import React, { useState, useCallback, useMemo } from 'react';
import { createRoot } from 'react-dom/client';
import {
    DndContext,
    DragEndEvent,
    DragOverlay,
    DragStartEvent,
    MouseSensor,
    TouchSensor,
    useSensor,
    useSensors,
    useDraggable,
    useDroppable,
} from '@dnd-kit/core';
import ErrorBoundary from './components/ErrorBoundary';

const translated = {
    storage: 'Storage',
    overview: 'Overview',
    storageOverview: 'Storage overview',
    overviewHint: 'Tap a mini-grid to switch storages',
    moveMode: 'Move Mode',
    moveModeHint: 'Select a bottle, then select destination',
    source: 'Source',
    destination: 'Destination',
    selectBottle: 'Select a bottle to move',
    selectDestination: 'Now select an empty cell in the destination',
    cancelMove: 'Cancel',
    tapToSeeDetails: 'Tap a bottle to see details',
    dragToMove: 'Long press and drag to move bottles',
    loading: 'Loading...',
    noStorageData: 'No storage data available',
    storageNotFound: 'Storage not found',
    cellOccupied: 'Cell is already occupied',
    movedSuccessfully: 'Bottle moved successfully',
    moveFailed: 'Move failed',
    utilisation: 'Utilisation',
    full: 'full',
    slotsUsed: 'slots used',
    noGridConfigured: 'No grid configured',
};

interface WineInfo {
    id: number;
    name: string;
    vintage: number | null;
    wine_type: string;
    wine_type_class?: string;
    country: string;
    item_id: number;
    rating: number | null;
}

// API response item (without 'active' field)
interface StorageItemData {
    row: number;
    column: number;
    wine: WineInfo;
}

interface PlannedMoveData {
    row: number;
    column: number;
    description: string;
}

// Fully-built grid cell (with 'active' field computed client-side)
interface CellData {
    row: number;
    column: number;
    wine: WineInfo | null;
    active: boolean;
    plannedMove: string | null;
}

interface StorageData {
    id: number;
    name: string;
    rows: number;
    columns: number;
    used_slots: number;
    total_slots: number;
    utilization_percent: number;
    cell_mask: [number, number][] | null;
    items: StorageItemData[];
    planned_moves: PlannedMoveData[];
}

interface AllStoragesData {
    storages: StorageData[];
    current_storage_id: number;
    item_url_prefix: string;
}

// Convert wine type display string to CSS class suffix
const getWineTypeClass = (wineType: string | null | undefined): string => {
    if (!wineType) return '';
    const typeMap: Record<string, string> = {
        'red': 'red',
        'white': 'white',
        'rose': 'rose',
        'rosé': 'rose',
        'sparkling': 'sparkling',
        'dessert': 'dessert',
        'fortified': 'fortified',
        'orange': 'orange',
        'cask-bourbon': 'cask-bourbon',
        'cask-sherry': 'cask-sherry',
        'cask-other': 'cask-other',
    };
    const normalized = wineType.toLowerCase();
    return typeMap[normalized] || '';
};

interface TooltipProps {
    wine: WineInfo;
    position: { x: number; y: number };
    itemUrlPrefix: string;
}

const getBottleDetailUrl = (itemUrlPrefix: string, wine: WineInfo): string => (
    `${itemUrlPrefix}${wine.id}/?storage_item=${encodeURIComponent(String(wine.item_id))}`
);

const getStorageOptionLabel = (storage: StorageData): string => (
    `${storage.name} (${storage.rows}x${storage.columns}, ${storage.utilization_percent}% ${translated.full})`
);

const getStorageUtilizationLabel = (storage: StorageData): string => {
    if (storage.total_slots <= 0) {
        return `${translated.utilisation}: ${storage.used_slots} ${translated.slotsUsed}`;
    }

    return `${translated.utilisation}: ${storage.used_slots}/${storage.total_slots} ${translated.slotsUsed} (${storage.utilization_percent}% ${translated.full})`;
};

const renderStorageMeta = (storage: StorageData, className = '') => (
    <div className={`storage-grid__storage-meta${className ? ` ${className}` : ''}`}>
        <span className="storage-grid__storage-meta-item">
            {storage.rows}x{storage.columns}
        </span>
        <span className="storage-grid__storage-meta-item">
            {getStorageUtilizationLabel(storage)}
        </span>
    </div>
);

const getCellClassName = (
    cell: CellData,
    options: {
        isDragging?: boolean;
        isOver?: boolean;
        extraClasses?: string[];
    } = {}
): string => {
    const {
        isDragging = false,
        isOver = false,
        extraClasses = [],
    } = options;
    const classNames = ['storage-grid__cell', ...extraClasses];
    const hasWine = cell.wine !== null;
    const isInactive = !cell.active;

    if (isInactive) {
        classNames.push('storage-grid__cell--inactive');
    } else if (hasWine) {
        classNames.push('storage-grid__cell--filled');
        const wineTypeClass = getWineTypeClass(cell.wine?.wine_type_class ?? cell.wine?.wine_type);
        if (wineTypeClass) classNames.push(`storage-grid__cell--${wineTypeClass}`);
    }
    if (cell.plannedMove) classNames.push('storage-grid__cell--planned');

    if (isDragging) classNames.push('storage-grid__cell--dragging');
    if (isOver && !hasWine && !isInactive) classNames.push('storage-grid__cell--drag-over');

    return classNames.join(' ');
};

const getCellPositionFromElement = (element: HTMLElement): { clientX: number; clientY: number } => {
    const rect = element.getBoundingClientRect();
    return {
        clientX: rect.left + (rect.width / 2),
        clientY: rect.top + (rect.height / 2),
    };
};

const focusGridCell = (
    currentTarget: HTMLElement,
    row: number,
    column: number,
    rowStep = 0,
    columnStep = 0,
) => {
    const gridId = currentTarget.dataset.gridId;
    if (!gridId) return;

    let nextRow = row;
    let nextColumn = column;

    while (true) {
        const selector = `[data-grid-id="${gridId}"][data-row="${nextRow}"][data-column="${nextColumn}"]`;
        const nextCell = document.querySelector<HTMLElement>(selector);

        if (!nextCell) {
            return;
        }

        if (!(nextCell instanceof HTMLButtonElement) || !nextCell.disabled) {
            nextCell.focus();
            return;
        }

        if (rowStep === 0 && columnStep === 0) {
            return;
        }

        nextRow += rowStep;
        nextColumn += columnStep;
    }
};

const handleGridKeyDown = (
    event: React.KeyboardEvent<HTMLElement>,
    onActivate?: () => void,
) => {
    const currentRow = Number(event.currentTarget.dataset.row);
    const currentColumn = Number(event.currentTarget.dataset.column);

    switch (event.key) {
    case 'ArrowUp':
        event.preventDefault();
        focusGridCell(event.currentTarget, currentRow - 1, currentColumn, -1, 0);
        break;
    case 'ArrowDown':
        event.preventDefault();
        focusGridCell(event.currentTarget, currentRow + 1, currentColumn, 1, 0);
        break;
    case 'ArrowLeft':
        event.preventDefault();
        focusGridCell(event.currentTarget, currentRow, currentColumn - 1, 0, -1);
        break;
    case 'ArrowRight':
        event.preventDefault();
        focusGridCell(event.currentTarget, currentRow, currentColumn + 1, 0, 1);
        break;
    case 'Home':
        event.preventDefault();
        focusGridCell(event.currentTarget, currentRow, 1, 0, 1);
        break;
    case 'End':
        event.preventDefault();
        focusGridCell(event.currentTarget, currentRow, Number(event.currentTarget.dataset.maxColumn), 0, -1);
        break;
    case 'Enter':
    case ' ':
        event.preventDefault();
        onActivate?.();
        break;
    default:
        break;
    }
};

const getCellAriaLabel = (
    cell: CellData,
    storageName: string,
    context: 'browse' | 'source' | 'destination',
    hasSelectedBottle = false,
): string => {
    const location = `${storageName}, row ${cell.row}, column ${cell.column}`;

    if (!cell.active) {
        return `${location}. Unavailable cell.`;
    }

    const plannedMove = cell.plannedMove ? ` Intended occupant: ${cell.plannedMove}.` : '';
    if (cell.wine) {
        const details = [
            cell.wine.name,
            cell.wine.vintage ? String(cell.wine.vintage) : null,
            cell.wine.country || null,
            cell.wine.wine_type || null,
        ].filter(Boolean).join(', ');

        if (context === 'source') {
            return `${location}. ${details}.${plannedMove} Press Enter to select this bottle to move.`;
        }

        if (context === 'destination') {
            return `${location}. ${details}.${plannedMove} Destination occupied. Choose an empty cell.`;
        }

        return `${location}. ${details}.${plannedMove} Press Enter to open bottle details.`;
    }

    if (context === 'destination' && hasSelectedBottle) {
        return `${location}. Empty cell.${plannedMove} Press Enter to move the selected bottle here.`;
    }

    if (context === 'source') {
        return `${location}. Empty cell.${plannedMove} Select a bottle to move.`;
    }

    return `${location}. Empty cell.${plannedMove}`;
};

const Tooltip: React.FC<TooltipProps> = ({ wine, position, itemUrlPrefix }) => {
    const tooltipRef = React.useRef<HTMLDivElement>(null);
    const [adjustedPosition, setAdjustedPosition] = React.useState({ x: position.x, y: position.y });
    const detailUrl = getBottleDetailUrl(itemUrlPrefix, wine);

    React.useLayoutEffect(() => {
        if (tooltipRef.current) {
            const tooltip = tooltipRef.current;
            const rect = tooltip.getBoundingClientRect();
            const padding = 10;

            let x = position.x + padding;
            let y = position.y + padding;

            // Adjust if tooltip would go off right edge
            if (x + rect.width > window.innerWidth - padding) {
                x = position.x - rect.width - padding;
            }

            // Adjust if tooltip would go off bottom edge
            if (y + rect.height > window.innerHeight - padding) {
                y = position.y - rect.height - padding;
            }

            // Ensure tooltip doesn't go off left or top edge
            x = Math.max(padding, x);
            y = Math.max(padding, y);

            setAdjustedPosition({ x, y });
        }
    }, [position.x, position.y]);

    return (
        <div
            ref={tooltipRef}
            className="storage-grid__tooltip"
            style={{
                position: 'fixed',
                left: adjustedPosition.x,
                top: adjustedPosition.y,
                zIndex: 1000,
            }}
        >
            <a
                href={detailUrl}
                className="tooltip__name tooltip__name--link"
                onClick={(e) => {
                    e.stopPropagation();
                }}
                onTouchEnd={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    window.location.href = detailUrl;
                }}
            >
                {wine.name}
            </a>
            {wine.vintage && <div className="tooltip__vintage">{wine.vintage}</div>}
            {wine.wine_type && <div className="tooltip__type">{wine.wine_type}</div>}
            {wine.country && <div className="tooltip__country">{wine.country}</div>}
            {wine.rating !== null && wine.rating !== undefined && (
                <div className="tooltip__rating">
                    {Array.from({ length: wine.rating }, (_, i) => (
                        <i key={i} className="fa-solid fa-star" />
                    ))}
                </div>
            )}
        </div>
    );
};

// Render star rating for grid cells
const RatingStars: React.FC<{ rating: number | null; maxRating?: number }> = ({ rating, maxRating = 3 }) => {
    if (rating === null || rating === undefined) return null;

    const stars = Math.min(rating, maxRating);
    return (
        <span className="storage-grid__rating">
            {Array.from({ length: stars }, (_, i) => (
                <i key={i} className="fa-solid fa-star" />
            ))}
        </span>
    );
};

// Draggable cell component
interface DraggableCellProps {
    cell: CellData;
    storageId: number;
    storageName: string;
    gridId: string;
    instructionsId: string;
    maxColumn: number;
    onShowTooltip: (wine: WineInfo, e: { clientX: number; clientY: number }) => void;
    onHideTooltip: () => void;
    onActivate: (cell: CellData) => void;
    isDragActive: boolean;
}

const DraggableCell: React.FC<DraggableCellProps> = ({
    cell,
    storageId,
    storageName,
    gridId,
    instructionsId,
    maxColumn,
    onShowTooltip,
    onHideTooltip,
    onActivate,
    isDragActive,
}) => {
    const id = `cell-${storageId}-${cell.row}-${cell.column}`;
    const hasWine = cell.wine !== null;
    const isInactive = !cell.active;

    const { attributes, listeners, setNodeRef: setDragRef, isDragging } = useDraggable({
        id,
        data: { cell, storageId },
        disabled: !hasWine || isInactive,
    });

    const { setNodeRef: setDropRef, isOver } = useDroppable({
        id,
        data: { cell, storageId },
        disabled: hasWine || isInactive, // Can't drop on occupied or inactive cell
    });

    // Combine refs
    const setNodeRef = (node: HTMLElement | null) => {
        setDragRef(node);
        setDropRef(node);
    };

    const handleMouseEnter = (e: React.MouseEvent) => {
        if (cell.wine && !isDragActive) {
            onShowTooltip(cell.wine, { clientX: e.clientX, clientY: e.clientY });
        }
    };

    const handleTouchEnd = (e: React.TouchEvent) => {
        // Show tooltip on tap (if not dragging)
        if (cell.wine && !isDragActive && e.changedTouches.length > 0) {
            const touch = e.changedTouches[0];
            onShowTooltip(cell.wine, { clientX: touch.clientX, clientY: touch.clientY });
        }
    };

    return (
        <button
            type="button"
            ref={setNodeRef}
            className={getCellClassName(cell, { isDragging, isOver })}
            {...listeners}
            {...attributes}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={onHideTooltip}
            onTouchEnd={handleTouchEnd}
            onFocus={(e) => {
                if (cell.wine && !isDragActive) {
                    onShowTooltip(cell.wine, getCellPositionFromElement(e.currentTarget));
                }
            }}
            onBlur={onHideTooltip}
            onKeyDown={(e) => handleGridKeyDown(e, () => onActivate(cell))}
            title={hasWine ? cell.wine!.name : `Empty (${cell.row}, ${cell.column})`}
            aria-label={getCellAriaLabel(cell, storageName, 'browse')}
            aria-describedby={instructionsId}
            data-grid-id={gridId}
            data-row={cell.row}
            data-column={cell.column}
            data-max-column={maxColumn}
            disabled={isInactive}
        >
            {hasWine && !isDragging && (
                <div className="storage-grid__bottle">
                    <i className="fa-solid fa-wine-bottle" aria-hidden="true" />
                    <RatingStars rating={cell.wine!.rating} />
                </div>
            )}
            {cell.plannedMove && (
                <i className="fa-solid fa-route storage-grid__planned-indicator" aria-hidden="true" />
            )}
        </button>
    );
};

// Drag overlay component shown during drag
const DragOverlayContent: React.FC<{ wine: WineInfo }> = ({ wine }) => {
    const wineTypeClass = getWineTypeClass(wine.wine_type_class ?? wine.wine_type);
    return (
        <div className={`storage-grid__cell storage-grid__cell--filled storage-grid__cell--overlay${wineTypeClass ? ` storage-grid__cell--${wineTypeClass}` : ''}`}>
            <div className="storage-grid__bottle">
                <i className="fa-solid fa-wine-bottle" />
                <RatingStars rating={wine.rating} />
            </div>
        </div>
    );
};

interface StorageGridProps {
    initialStorageId?: number;
}

const StorageGrid: React.FC<StorageGridProps> = ({ initialStorageId }) => {
    const [data, setData] = useState<AllStoragesData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [tooltip, setTooltip] = useState<{ wine: WineInfo; position: { x: number; y: number } } | null>(null);
    const [sourceStorageId, setSourceStorageId] = useState<number | null>(null);
    const [targetStorageId, setTargetStorageId] = useState<number | null>(null);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    const [moveMode, setMoveMode] = useState(false);
    const [selectedBottle, setSelectedBottle] = useState<{ cell: CellData; storageId: number } | null>(null);
    const [activeItem, setActiveItem] = useState<{ cell: CellData; storageId: number } | null>(null);
    const [itemUrlPrefix, setItemUrlPrefix] = useState('/wine/');

    // Configure sensors for mouse and touch
    // TouchSensor with delay to distinguish scroll from drag
    const mouseSensor = useSensor(MouseSensor, {
        activationConstraint: {
            distance: 5, // Start drag after moving 5px
        },
    });

    const touchSensor = useSensor(TouchSensor, {
        activationConstraint: {
            delay: 250, // 250ms long press before drag starts
            tolerance: 5, // Allow 5px movement during delay
        },
    });

    const sensors = useSensors(mouseSensor, touchSensor);

    // Fetch data on mount
    React.useEffect(() => {
        fetchStorageData();
    }, []);

    const fetchStorageData = async () => {
        try {
            const url = initialStorageId
                ? `/api/storage/grid-data/?storage_id=${initialStorageId}`
                : '/api/storage/grid-data/';
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load storage data');
            const json = await response.json();
            setData(json);
            setSourceStorageId(json.current_storage_id);
            if (json.item_url_prefix) setItemUrlPrefix(json.item_url_prefix);
            // Set target storage - prefer last used (localStorage), then another storage, then same as source
            const savedTargetId = localStorage.getItem('storage_grid_target_id');
            const savedTarget = savedTargetId
                ? json.storages.find((s: StorageData) => s.id === parseInt(savedTargetId))
                : null;
            const otherStorage = json.storages.find((s: StorageData) => s.id !== json.current_storage_id);
            setTargetStorageId(savedTarget?.id || otherStorage?.id || json.current_storage_id);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    const moveBottle = async (itemId: number, targetStorageIdParam: number, targetRow: number, targetColumn: number) => {
        const csrfToken = document.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]')?.value || '';

        const response = await fetch('/api/storage/move-bottle/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
                item_id: itemId,
                target_storage_id: targetStorageIdParam,
                target_row: targetRow,
                target_column: targetColumn,
            }),
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || translated.moveFailed);
        }

        return response.json();
    };

    const handleDragStart = (event: DragStartEvent) => {
        const { active } = event;
        const data = active.data.current as { cell: CellData; storageId: number } | undefined;
        if (data) {
            setActiveItem(data);
            setTooltip(null); // Hide tooltip during drag
        }
    };

    const handleDragEnd = async (event: DragEndEvent) => {
        const { active, over } = event;
        setActiveItem(null);

        if (!over) return;

        const activeData = active.data.current as { cell: CellData; storageId: number } | undefined;
        const overData = over.data.current as { cell: CellData; storageId: number } | undefined;

        if (!activeData || !overData || !activeData.cell.wine) return;

        // Don't allow drop on same cell
        if (activeData.storageId === overData.storageId &&
            activeData.cell.row === overData.cell.row &&
            activeData.cell.column === overData.cell.column) {
            return;
        }

        // Don't allow drop on occupied cell
        if (overData.cell.wine) {
            setMessage({ type: 'error', text: translated.cellOccupied });
            return;
        }

        try {
            await moveBottle(
                activeData.cell.wine.item_id,
                overData.storageId,
                overData.cell.row,
                overData.cell.column
            );
            await fetchStorageData();
            setMessage({ type: 'success', text: translated.movedSuccessfully });
        } catch (e) {
            setMessage({ type: 'error', text: e instanceof Error ? e.message : translated.moveFailed });
        }
    };

    // Handle click in move mode - select bottle from source, then destination cell
    const handleMoveModeClick = useCallback(async (cell: CellData, storageId: number, isSource: boolean) => {
        if (isSource) {
            // Clicking on source grid - select a bottle
            if (cell.wine) {
                setSelectedBottle({ cell, storageId });
            }
        } else {
            // Clicking on destination grid - move the selected bottle here
            if (selectedBottle && !cell.wine) {
                try {
                    await moveBottle(selectedBottle.cell.wine!.item_id, storageId, cell.row, cell.column);
                    await fetchStorageData();
                    setMessage({ type: 'success', text: translated.movedSuccessfully });
                    setSelectedBottle(null);
                } catch (e) {
                    setMessage({ type: 'error', text: e instanceof Error ? e.message : translated.moveFailed });
                }
            } else if (cell.wine) {
                setMessage({ type: 'error', text: translated.cellOccupied });
            }
        }
    }, [selectedBottle]);

    const handleShowTooltip = useCallback((wine: WineInfo, e: { clientX: number; clientY: number }) => {
        setTooltip({ wine, position: { x: e.clientX, y: e.clientY } });
    }, []);

    const handleHideTooltip = useCallback(() => {
        setTooltip(null);
    }, []);

    const toggleMoveMode = () => {
        setMoveMode(!moveMode);
        setSelectedBottle(null);
    };

    // Clear message after 3 seconds
    React.useEffect(() => {
        if (message) {
            const timer = setTimeout(() => setMessage(null), 3000);
            return () => clearTimeout(timer);
        }
    }, [message]);

    // Close tooltip when tapping outside on mobile
    React.useEffect(() => {
        const handleDocumentTouch = (e: TouchEvent) => {
            const target = e.target as HTMLElement;
            if (tooltip && !target.closest('.storage-grid__cell') && !target.closest('.storage-grid__tooltip')) {
                setTooltip(null);
            }
        };

        document.addEventListener('touchstart', handleDocumentTouch);
        return () => document.removeEventListener('touchstart', handleDocumentTouch);
    }, [tooltip]);

    // Build grid helper - memoized
    const buildGrid = useCallback((storage: StorageData): CellData[][] => {
        const maskSet: Set<string> | null = storage.cell_mask
            ? new Set(storage.cell_mask.map(([r, c]) => `${r},${c}`))
            : null;
        // Pre-index items and planned_moves by "row,col" for O(1) lookups
        const itemIndex = new Map<string, typeof storage.items[number]>();
        for (const item of storage.items) {
            const key = `${item.row},${item.column}`;
            if (!itemIndex.has(key)) itemIndex.set(key, item);
        }
        const plannedMoveIndex = new Map<string, typeof storage.planned_moves[number]>();
        for (const move of storage.planned_moves) {
            const key = `${move.row},${move.column}`;
            if (!plannedMoveIndex.has(key)) plannedMoveIndex.set(key, move);
        }
        const grid: CellData[][] = [];
        for (let row = 1; row <= storage.rows; row++) {
            const rowCells: CellData[] = [];
            for (let col = 1; col <= storage.columns; col++) {
                const key = `${row},${col}`;
                const item = itemIndex.get(key);
                const plannedMove = plannedMoveIndex.get(key);
                const active = maskSet === null || maskSet.has(key);
                rowCells.push({
                    row,
                    column: col,
                    wine: item?.wine || null,
                    active,
                    plannedMove: plannedMove?.description || null,
                });
            }
            grid.push(rowCells);
        }
        return grid;
    }, []);

    // Find storages
    const sourceStorage = data?.storages.find(s => s.id === sourceStorageId);
    const targetStorage = data?.storages.find(s => s.id === targetStorageId);

    // Memoize grid computations
    const sourceGrid = useMemo(() => sourceStorage ? buildGrid(sourceStorage) : [], [buildGrid, sourceStorage]);
    const targetGrid = useMemo(() => targetStorage ? buildGrid(targetStorage) : [], [buildGrid, targetStorage]);
    const overviewGrids = useMemo(
        () => data?.storages.map((storage) => ({ storage, grid: buildGrid(storage) })) ?? [],
        [buildGrid, data]
    );

    const handleBrowseCellActivate = useCallback((cell: CellData) => {
        if (!cell.wine) return;
        window.location.href = getBottleDetailUrl(itemUrlPrefix, cell.wine);
    }, [itemUrlPrefix]);

    // Early returns after all hooks
    if (loading) return <div className="storage-grid__loading">{translated.loading}</div>;
    if (error) return <div className="storage-grid__error">Error: {error}</div>;
    if (!data) return <div className="storage-grid__empty">{translated.noStorageData}</div>;
    if (!sourceStorage) return <div className="storage-grid__error">{translated.storageNotFound}</div>;

    // Render a single grid pane for move mode
    const renderGridPane = (storage: StorageData, grid: CellData[][], isSource: boolean) => (
        <div className="storage-grid__pane">
            <div className="storage-grid__pane-header">
                <label htmlFor={isSource ? 'source-select' : 'target-select'}>
                    {isSource ? translated.source : translated.destination}:
                </label>
                <select
                    id={isSource ? 'source-select' : 'target-select'}
                    value={storage.id}
                    onChange={(e) => {
                        const id = Number(e.target.value);
                        if (isSource) {
                            setSourceStorageId(id);
                        } else {
                            setTargetStorageId(id);
                            localStorage.setItem('storage_grid_target_id', String(id));
                        }
                    }}
                    className="storage-grid__select"
                >
                    {data.storages.map(s => (
                        <option key={s.id} value={s.id}>
                            {getStorageOptionLabel(s)}
                        </option>
                    ))}
                </select>
            </div>

            <div className="storage-grid__header">
                <div className="storage-grid__corner" />
                {Array.from({ length: storage.columns }, (_, i) => (
                    <div key={i} className="storage-grid__col-label">{i + 1}</div>
                ))}
            </div>

            <div className="storage-grid__body" role="group" aria-label={`${storage.name} storage grid`}>
                {grid.map((row, rowIdx) => (
                    <div key={rowIdx} className="storage-grid__row">
                        <div className="storage-grid__row-label">{rowIdx + 1}</div>
                        {row.map((cell, colIdx) => {
                            const isInactive = !cell.active;
                            const isSelectedForMove = selectedBottle?.cell.row === cell.row &&
                                selectedBottle?.cell.column === cell.column &&
                                selectedBottle?.storageId === storage.id;

                            const extraClasses = [];
                            if (isSelectedForMove) extraClasses.push('storage-grid__cell--selected-for-move');
                            if (!isSource && !cell.wine && !isInactive && selectedBottle) {
                                extraClasses.push('storage-grid__cell--drop-target');
                            }

                            return (
                                <button
                                    type="button"
                                    key={`${rowIdx}-${colIdx}`}
                                    className={getCellClassName(cell, { extraClasses })}
                                    onClick={() => !isInactive && handleMoveModeClick(cell, storage.id, isSource)}
                                    onMouseEnter={(e) => cell.wine && handleShowTooltip(cell.wine, e)}
                                    onMouseLeave={handleHideTooltip}
                                    onFocus={(e) => {
                                        if (cell.wine) {
                                            handleShowTooltip(cell.wine, getCellPositionFromElement(e.currentTarget));
                                        }
                                    }}
                                    onBlur={handleHideTooltip}
                                    onTouchStart={(e) => {
                                        if (cell.wine && e.touches.length > 0) {
                                            const touch = e.touches[0];
                                            handleShowTooltip(cell.wine, { clientX: touch.clientX, clientY: touch.clientY });
                                            e.stopPropagation();
                                        }
                                    }}
                                    onKeyDown={(e) => {
                                        handleGridKeyDown(e, () => {
                                            if (!isInactive) {
                                                handleMoveModeClick(cell, storage.id, isSource);
                                            }
                                        });
                                    }}
                                    title={cell.wine ? cell.wine.name : `Empty (${cell.row}, ${cell.column})`}
                                    aria-label={getCellAriaLabel(
                                        cell,
                                        storage.name,
                                        isSource ? 'source' : 'destination',
                                        Boolean(selectedBottle),
                                    )}
                                    aria-describedby="storage-grid-move-instructions"
                                    aria-pressed={isSource && isSelectedForMove ? true : undefined}
                                    data-grid-id={`${isSource ? 'source' : 'destination'}-${storage.id}`}
                                    data-row={cell.row}
                                    data-column={cell.column}
                                    data-max-column={storage.columns}
                                    disabled={isInactive}
                                >
                                    {cell.wine && (
                                        <div className="storage-grid__bottle">
                                            <i className="fa-solid fa-wine-bottle" aria-hidden="true" />
                                            <RatingStars rating={cell.wine.rating} />
                                        </div>
                                    )}
                                    {cell.plannedMove && (
                                        <i className="fa-solid fa-route storage-grid__planned-indicator" aria-hidden="true" />
                                    )}
                                </button>
                            );
                        })}
                    </div>
                ))}
            </div>
            {renderStorageMeta(storage, 'storage-grid__storage-meta--after-grid')}
        </div>
    );

    const renderOverview = () => {
        if (data.storages.length <= 1) return null;

        return (
            <section className="storage-grid__overview" aria-label={translated.storageOverview}>
                <div className="storage-grid__overview-header">
                    <div>
                        <div className="storage-grid__overview-eyebrow">{translated.overview}</div>
                        <h2 className="storage-grid__overview-title">{translated.storageOverview}</h2>
                    </div>
                    <p className="storage-grid__overview-hint">{translated.overviewHint}</p>
                </div>

                <div className="storage-grid__overview-list">
                    {overviewGrids.map(({ storage, grid }) => (
                        <button
                            key={storage.id}
                            type="button"
                            className={`storage-grid__overview-card${storage.id === sourceStorageId ? ' storage-grid__overview-card--active' : ''}`}
                            onClick={() => setSourceStorageId(storage.id)}
                            aria-pressed={storage.id === sourceStorageId}
                        >
                            <div className="storage-grid__overview-card-header">
                                <span className="storage-grid__overview-card-title">{storage.name}</span>
                                <span className="storage-grid__overview-card-dimensions">
                                    {storage.rows}x{storage.columns}
                                </span>
                            </div>

                            <div className="storage-grid__overview-card-meta">
                                {getStorageUtilizationLabel(storage)}
                            </div>

                            {storage.rows > 0 && storage.columns > 0 ? (
                                <div
                                    className="storage-grid__mini-grid"
                                    style={{ gridTemplateColumns: `repeat(${storage.columns}, minmax(0, 1fr))` }}
                                    aria-hidden="true"
                                >
                                    {grid.map((row, rowIdx) => row.map((cell, colIdx) => (
                                        <div
                                            key={`${storage.id}-${rowIdx}-${colIdx}`}
                                            className={getCellClassName(cell, { extraClasses: ['storage-grid__mini-cell'] })}
                                        />
                                    )))}
                                </div>
                            ) : (
                                <div className="storage-grid__overview-card-empty">
                                    {translated.noGridConfigured}
                                </div>
                            )}
                        </button>
                    ))}
                </div>
            </section>
        );
    };

    // Move mode: dual pane view (without dnd-kit, uses click-based selection)
    if (moveMode && targetStorage) {
        return (
            <div className="storage-grid storage-grid--move-mode">
                {/* Move mode toggle */}
                <div className="storage-grid__controls">
                    <button
                        type="button"
                        className="storage-grid__mode-btn storage-grid__mode-btn--active"
                        onClick={toggleMoveMode}
                    >
                        <i className="fa-solid fa-arrows-left-right" /> {translated.moveMode}
                    </button>
                    {selectedBottle && (
                        <button
                            type="button"
                            className="storage-grid__cancel-btn"
                            onClick={() => setSelectedBottle(null)}
                        >
                            {translated.cancelMove}
                        </button>
                    )}
                </div>

                {/* Message */}
                {message && (
                    <div
                        className={`storage-grid__message storage-grid__message--${message.type}`}
                        role={message.type === 'error' ? 'alert' : 'status'}
                    >
                        {message.text}
                    </div>
                )}

                {/* Move mode hint */}
                <div className="storage-grid__move-hint">
                    {selectedBottle ? (
                        <><i className="fa-solid fa-hand-pointer" aria-hidden="true" /> {translated.selectDestination}</>
                    ) : (
                        <><i className="fa-solid fa-wine-bottle" aria-hidden="true" /> {translated.selectBottle}</>
                    )}
                </div>
                <p id="storage-grid-move-instructions" className="visually-hidden">
                    Use Tab or the arrow keys to move between cells. Press Enter to select a bottle in
                    the source grid, then press Enter on an empty destination cell to move it.
                </p>

                {/* Dual pane layout */}
                <div className="storage-grid__dual-pane">
                    {renderGridPane(sourceStorage, sourceGrid, true)}
                    <div className="storage-grid__arrow">
                        <i className="fa-solid fa-arrow-right" />
                    </div>
                    {renderGridPane(targetStorage, targetGrid, false)}
                </div>

                {/* Tooltip */}
                {tooltip && <Tooltip wine={tooltip.wine} position={tooltip.position} itemUrlPrefix={itemUrlPrefix} />}
            </div>
        );
    }

    // Normal single-grid view with dnd-kit drag and drop
    return (
        <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
        >
            <div className="storage-grid">
                {/* Controls */}
                <div className="storage-grid__controls">
                    <label htmlFor="storage-select">{translated.storage}:</label>
                    <select
                        id="storage-select"
                        value={sourceStorageId || ''}
                        onChange={(e) => setSourceStorageId(Number(e.target.value))}
                        className="storage-grid__select"
                    >
                        {data.storages.map(s => (
                            <option key={s.id} value={s.id}>
                                {getStorageOptionLabel(s)}
                            </option>
                        ))}
                    </select>

                    {data.storages.length > 1 && (
                        <button
                            type="button"
                            className="storage-grid__mode-btn"
                            onClick={toggleMoveMode}
                        >
                            <i className="fa-solid fa-arrows-left-right" /> {translated.moveMode}
                        </button>
                    )}
                </div>

                {/* Message */}
                {message && (
                    <div
                        className={`storage-grid__message storage-grid__message--${message.type}`}
                        role={message.type === 'error' ? 'alert' : 'status'}
                    >
                        {message.text}
                    </div>
                )}
                <p id="storage-grid-browse-instructions" className="visually-hidden">
                    Use Tab or the arrow keys to move between cells. Press Enter on a filled cell to
                    open that bottle. Switch to move mode to move bottles without using drag and drop.
                </p>

                {/* Grid header with column numbers */}
                <div className="storage-grid__header">
                    <div className="storage-grid__corner" />
                    {Array.from({ length: sourceStorage.columns }, (_, i) => (
                        <div key={i} className="storage-grid__col-label">{i + 1}</div>
                    ))}
                </div>

                {/* Grid rows */}
                <div className="storage-grid__body">
                    {sourceGrid.map((row, rowIdx) => (
                        <div key={rowIdx} className="storage-grid__row">
                            <div className="storage-grid__row-label">{rowIdx + 1}</div>
                            {row.map((cell, colIdx) => (
                                <DraggableCell
                                    key={`${rowIdx}-${colIdx}`}
                                    cell={cell}
                                    storageId={sourceStorageId!}
                                    storageName={sourceStorage.name}
                                    gridId={`browse-${sourceStorage.id}`}
                                    instructionsId="storage-grid-browse-instructions"
                                    maxColumn={sourceStorage.columns}
                                    onShowTooltip={handleShowTooltip}
                                    onHideTooltip={handleHideTooltip}
                                    onActivate={handleBrowseCellActivate}
                                    isDragActive={activeItem !== null}
                                />
                            ))}
                        </div>
                    ))}
                </div>
                {renderStorageMeta(sourceStorage, 'storage-grid__storage-meta--after-grid')}

                {/* Drag overlay */}
                <DragOverlay>
                    {activeItem?.cell.wine && (
                        <DragOverlayContent wine={activeItem.cell.wine} />
                    )}
                </DragOverlay>

                {/* Tooltip */}
                {tooltip && <Tooltip wine={tooltip.wine} position={tooltip.position} itemUrlPrefix={itemUrlPrefix} />}

                {/* Instructions */}
                <div className="storage-grid__instructions">
                    <p><i className="fa-solid fa-hand-pointer" /> {translated.tapToSeeDetails}</p>
                    <p><i className="fa-solid fa-hand-back-fist" /> {translated.dragToMove}</p>
                </div>

                {renderOverview()}
            </div>
        </DndContext>
    );
};

const initStorageGrid = () => {
    const container = document.getElementById('storage-grid-container');
    if (container) {
        // Get initial storage ID from data attribute
        const storageIdAttr = container.getAttribute('data-storage-id');
        const initialStorageId = storageIdAttr ? parseInt(storageIdAttr, 10) : undefined;
        const root = createRoot(container);
        root.render(<ErrorBoundary><StorageGrid initialStorageId={initialStorageId} /></ErrorBoundary>);
    }
};

document.addEventListener('DOMContentLoaded', initStorageGrid, false);

export default StorageGrid;
