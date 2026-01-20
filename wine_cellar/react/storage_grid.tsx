import React, { useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
// @ts-ignore
import django from 'django';

const translated = {
    storage: django.gettext('Storage'),
    moveMode: django.gettext('Move Mode'),
    moveModeHint: django.gettext('Select a bottle, then select destination'),
    source: django.gettext('Source'),
    destination: django.gettext('Destination'),
    selectBottle: django.gettext('Select a bottle to move'),
    selectDestination: django.gettext('Now select an empty cell in the destination'),
    cancelMove: django.gettext('Cancel'),
    tapToSeeDetails: django.gettext('Tap a bottle to see details'),
    dragToMove: django.gettext('Drag and drop to move bottles'),
    loading: django.gettext('Loading...'),
    noStorageData: django.gettext('No storage data available'),
    storageNotFound: django.gettext('Storage not found'),
    cellOccupied: django.gettext('Cell is already occupied'),
    movedSuccessfully: django.gettext('Bottle moved successfully'),
    moveFailed: django.gettext('Move failed'),
};

interface WineInfo {
    id: number;
    name: string;
    vintage: number | null;
    wine_type: string;
    country: string;
    item_id: number;
    rating: number | null;
}

interface CellData {
    row: number;
    column: number;
    wine: WineInfo | null;
}

interface StorageData {
    id: number;
    name: string;
    rows: number;
    columns: number;
    items: CellData[];
}

interface AllStoragesData {
    storages: StorageData[];
    current_storage_id: number;
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
    };
    const normalized = wineType.toLowerCase();
    return typeMap[normalized] || '';
};

interface TooltipProps {
    wine: WineInfo;
    position: { x: number; y: number };
}

const Tooltip: React.FC<TooltipProps> = ({ wine, position }) => {
    const tooltipRef = React.useRef<HTMLDivElement>(null);
    const [adjustedPosition, setAdjustedPosition] = React.useState({ x: position.x, y: position.y });

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
                href={`/wine/${wine.id}/`}
                className="tooltip__name tooltip__name--link"
                onClick={(e) => {
                    e.stopPropagation();
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

interface GridCellProps {
    cell: CellData;
    isSelected: boolean;
    isDragOver: boolean;
    onSelect: (cell: CellData) => void;
    onDragStart: (cell: CellData) => void;
    onDragOver: (cell: CellData) => void;
    onDrop: (cell: CellData) => void;
    onMouseEnter: (wine: WineInfo, e: React.MouseEvent) => void;
    onMouseLeave: () => void;
}

const GridCell: React.FC<GridCellProps> = ({
    cell,
    isSelected,
    isDragOver,
    onSelect,
    onDragStart,
    onDragOver,
    onDrop,
    onMouseEnter,
    onMouseLeave,
}) => {
    const hasWine = cell.wine !== null;
    
    const handleDragStart = (e: React.DragEvent) => {
        if (hasWine) {
            e.dataTransfer.effectAllowed = 'move';
            onDragStart(cell);
        }
    };
    
    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        onDragOver(cell);
    };
    
    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        onDrop(cell);
    };
    
    const handleMouseEnter = (e: React.MouseEvent) => {
        if (cell.wine) {
            onMouseEnter(cell.wine, e);
        }
    };

    const handleTouch = (e: React.TouchEvent) => {
        if (cell.wine && e.touches.length > 0) {
            const touch = e.touches[0];
            const mouseEvent = {
                clientX: touch.clientX,
                clientY: touch.clientY,
            } as React.MouseEvent;
            onMouseEnter(cell.wine, mouseEvent);
        }
    };

    let className = 'storage-grid__cell';
    if (hasWine) {
        className += ' storage-grid__cell--filled';
        const wineTypeClass = getWineTypeClass(cell.wine?.wine_type);
        if (wineTypeClass) className += ` storage-grid__cell--${wineTypeClass}`;
    }
    if (isSelected) className += ' storage-grid__cell--selected';
    if (isDragOver) className += ' storage-grid__cell--drag-over';
    
    return (
        <div
            className={className}
            draggable={hasWine}
            onClick={() => onSelect(cell)}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={onMouseLeave}
            onTouchStart={handleTouch}
            onTouchEnd={onMouseLeave}
            title={hasWine ? cell.wine!.name : `Empty (${cell.row}, ${cell.column})`}
        >
            {hasWine && (
                <div className="storage-grid__bottle">
                    <i className="fa-solid fa-wine-bottle" />
                    <RatingStars rating={cell.wine!.rating} />
                </div>
            )}
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
    const [selectedCell, setSelectedCell] = useState<CellData | null>(null);
    const [draggedCell, setDraggedCell] = useState<CellData | null>(null);
    const [dragOverCell, setDragOverCell] = useState<CellData | null>(null);
    const [tooltip, setTooltip] = useState<{ wine: WineInfo; position: { x: number; y: number } } | null>(null);
    const [sourceStorageId, setSourceStorageId] = useState<number | null>(null);
    const [targetStorageId, setTargetStorageId] = useState<number | null>(null);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    const [moveMode, setMoveMode] = useState(false);
    const [selectedBottle, setSelectedBottle] = useState<{ cell: CellData; storageId: number } | null>(null);
    
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
            // Set target to a different storage if available, otherwise same as source
            const otherStorage = json.storages.find((s: StorageData) => s.id !== json.current_storage_id);
            setTargetStorageId(otherStorage?.id || json.current_storage_id);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };
    
    const handleCellSelect = useCallback((cell: CellData) => {
        setSelectedCell(cell);
    }, []);
    
    const handleDragStart = useCallback((cell: CellData) => {
        setDraggedCell(cell);
    }, []);
    
    const handleDragOver = useCallback((cell: CellData) => {
        setDragOverCell(cell);
    }, []);
    
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
    
    const handleDrop = useCallback(async (targetCell: CellData) => {
        if (!draggedCell || !draggedCell.wine) {
            setDraggedCell(null);
            setDragOverCell(null);
            return;
        }
        
        // Don't allow drop on same cell
        if (draggedCell.row === targetCell.row && draggedCell.column === targetCell.column) {
            setDraggedCell(null);
            setDragOverCell(null);
            return;
        }
        
        // Don't allow drop on occupied cell
        if (targetCell.wine) {
            setMessage({ type: 'error', text: translated.cellOccupied });
            setDraggedCell(null);
            setDragOverCell(null);
            return;
        }
        
        try {
            await moveBottle(draggedCell.wine.item_id, sourceStorageId!, targetCell.row, targetCell.column);
            await fetchStorageData();
            setMessage({ type: 'success', text: translated.movedSuccessfully });
        } catch (e) {
            setMessage({ type: 'error', text: e instanceof Error ? e.message : translated.moveFailed });
        } finally {
            setDraggedCell(null);
            setDragOverCell(null);
        }
    }, [draggedCell, sourceStorageId]);
    
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
    
    const handleMouseEnter = useCallback((wine: WineInfo, e: React.MouseEvent) => {
        setTooltip({ wine, position: { x: e.clientX, y: e.clientY } });
    }, []);
    
    const handleMouseLeave = useCallback(() => {
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
    
    if (loading) return <div className="storage-grid__loading">{translated.loading}</div>;
    if (error) return <div className="storage-grid__error">Error: {error}</div>;
    if (!data) return <div className="storage-grid__empty">{translated.noStorageData}</div>;
    
    const sourceStorage = data.storages.find(s => s.id === sourceStorageId);
    const targetStorage = data.storages.find(s => s.id === targetStorageId);
    
    if (!sourceStorage) return <div className="storage-grid__error">{translated.storageNotFound}</div>;
    
    // Build grid helper
    const buildGrid = (storage: StorageData): CellData[][] => {
        const grid: CellData[][] = [];
        for (let row = 1; row <= storage.rows; row++) {
            const rowCells: CellData[] = [];
            for (let col = 1; col <= storage.columns; col++) {
                const item = storage.items.find(i => i.row === row && i.column === col);
                rowCells.push({
                    row,
                    column: col,
                    wine: item?.wine || null,
                });
            }
            grid.push(rowCells);
        }
        return grid;
    };
    
    const sourceGrid = buildGrid(sourceStorage);
    const targetGrid = targetStorage ? buildGrid(targetStorage) : [];
    
    // Render a single grid pane
    const renderGridPane = (storage: StorageData, grid: CellData[][], isSource: boolean) => (
        <div className="storage-grid__pane">
            <div className="storage-grid__pane-header">
                <label htmlFor={isSource ? 'source-select' : 'target-select'}>
                    {isSource ? translated.source : translated.destination}:
                </label>
                <select
                    id={isSource ? 'source-select' : 'target-select'}
                    value={storage.id}
                    onChange={(e) => isSource ? setSourceStorageId(Number(e.target.value)) : setTargetStorageId(Number(e.target.value))}
                    className="storage-grid__select"
                >
                    {data.storages.map(s => (
                        <option key={s.id} value={s.id}>
                            {s.name} ({s.rows}x{s.columns})
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
            
            <div className="storage-grid__body">
                {grid.map((row, rowIdx) => (
                    <div key={rowIdx} className="storage-grid__row">
                        <div className="storage-grid__row-label">{rowIdx + 1}</div>
                        {row.map((cell, colIdx) => {
                            const isSelectedForMove = selectedBottle?.cell.row === cell.row && 
                                selectedBottle?.cell.column === cell.column && 
                                selectedBottle?.storageId === storage.id;
                            
                            const wineTypeClass = cell.wine ? getWineTypeClass(cell.wine.wine_type) : '';

                            return (
                                <div
                                    key={`${rowIdx}-${colIdx}`}
                                    className={`storage-grid__cell${cell.wine ? ' storage-grid__cell--filled' : ''}${wineTypeClass ? ` storage-grid__cell--${wineTypeClass}` : ''}${isSelectedForMove ? ' storage-grid__cell--selected-for-move' : ''}${!isSource && !cell.wine && selectedBottle ? ' storage-grid__cell--drop-target' : ''}`}
                                    onClick={() => handleMoveModeClick(cell, storage.id, isSource)}
                                    onMouseEnter={(e) => cell.wine && handleMouseEnter(cell.wine, e)}
                                    onMouseLeave={handleMouseLeave}
                                    onTouchStart={(e) => {
                                        if (cell.wine && e.touches.length > 0) {
                                            const touch = e.touches[0];
                                            handleMouseEnter(cell.wine, { clientX: touch.clientX, clientY: touch.clientY } as React.MouseEvent);
                                        }
                                    }}
                                    onTouchEnd={handleMouseLeave}
                                    title={cell.wine ? cell.wine.name : `Empty (${cell.row}, ${cell.column})`}
                                >
                                    {cell.wine && (
                                        <div className="storage-grid__bottle">
                                            <i className="fa-solid fa-wine-bottle" />
                                            <RatingStars rating={cell.wine.rating} />
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                ))}
            </div>
        </div>
    );
    
    // Move mode: dual pane view
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
                    <div className={`storage-grid__message storage-grid__message--${message.type}`}>
                        {message.text}
                    </div>
                )}
                
                {/* Move mode hint */}
                <div className="storage-grid__move-hint">
                    {selectedBottle ? (
                        <><i className="fa-solid fa-hand-pointer" /> {translated.selectDestination}</>
                    ) : (
                        <><i className="fa-solid fa-wine-bottle" /> {translated.selectBottle}</>
                    )}
                </div>
                
                {/* Dual pane layout */}
                <div className="storage-grid__dual-pane">
                    {renderGridPane(sourceStorage, sourceGrid, true)}
                    <div className="storage-grid__arrow">
                        <i className="fa-solid fa-arrow-right" />
                    </div>
                    {renderGridPane(targetStorage, targetGrid, false)}
                </div>
                
                {/* Tooltip */}
                {tooltip && <Tooltip wine={tooltip.wine} position={tooltip.position} />}
            </div>
        );
    }
    
    // Normal single-grid view with drag and drop
    return (
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
                            {s.name} ({s.rows}x{s.columns})
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
                <div className={`storage-grid__message storage-grid__message--${message.type}`}>
                    {message.text}
                </div>
            )}
            
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
                            <GridCell
                                key={`${rowIdx}-${colIdx}`}
                                cell={cell}
                                isSelected={selectedCell?.row === cell.row && selectedCell?.column === cell.column}
                                isDragOver={dragOverCell?.row === cell.row && dragOverCell?.column === cell.column}
                                onSelect={handleCellSelect}
                                onDragStart={handleDragStart}
                                onDragOver={handleDragOver}
                                onDrop={handleDrop}
                                onMouseEnter={handleMouseEnter}
                                onMouseLeave={handleMouseLeave}
                            />
                        ))}
                    </div>
                ))}
            </div>
            
            {/* Tooltip */}
            {tooltip && <Tooltip wine={tooltip.wine} position={tooltip.position} />}
            
            {/* Instructions */}
            <div className="storage-grid__instructions">
                <p><i className="fa-solid fa-hand-pointer" /> {translated.tapToSeeDetails}</p>
                <p><i className="fa-solid fa-arrows-up-down-left-right" /> {translated.dragToMove}</p>
            </div>
        </div>
    );
};

const initStorageGrid = () => {
    const container = document.getElementById('storage-grid-container');
    if (container) {
        // Get initial storage ID from data attribute
        const storageIdAttr = container.getAttribute('data-storage-id');
        const initialStorageId = storageIdAttr ? parseInt(storageIdAttr, 10) : undefined;
        const root = createRoot(container);
        root.render(<StorageGrid initialStorageId={initialStorageId} />);
    }
};

document.addEventListener('DOMContentLoaded', initStorageGrid, false);

export default StorageGrid;
