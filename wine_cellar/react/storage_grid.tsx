import React, { useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';

interface WineInfo {
    id: number;
    name: string;
    vintage: number | null;
    wine_type: string;
    country: string;
    item_id: number;
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

interface TooltipProps {
    wine: WineInfo;
    position: { x: number; y: number };
}

const Tooltip: React.FC<TooltipProps> = ({ wine, position }) => {
    return (
        <div 
            className="storage-grid__tooltip"
            style={{
                position: 'fixed',
                left: position.x + 10,
                top: position.y + 10,
                zIndex: 1000,
            }}
        >
            <div className="tooltip__name">{wine.name}</div>
            {wine.vintage && <div className="tooltip__vintage">{wine.vintage}</div>}
            {wine.wine_type && <div className="tooltip__type">{wine.wine_type}</div>}
            {wine.country && <div className="tooltip__country">{wine.country}</div>}
        </div>
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
    
    let className = 'storage-grid__cell';
    if (hasWine) className += ' storage-grid__cell--filled';
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
            title={hasWine ? cell.wine!.name : `Empty (${cell.row}, ${cell.column})`}
        >
            {hasWine && (
                <div className="storage-grid__bottle">
                    <i className="fa-solid fa-wine-bottle" />
                </div>
            )}
        </div>
    );
};

const StorageGrid: React.FC = () => {
    const [data, setData] = useState<AllStoragesData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedCell, setSelectedCell] = useState<CellData | null>(null);
    const [draggedCell, setDraggedCell] = useState<CellData | null>(null);
    const [dragOverCell, setDragOverCell] = useState<CellData | null>(null);
    const [tooltip, setTooltip] = useState<{ wine: WineInfo; position: { x: number; y: number } } | null>(null);
    const [targetStorageId, setTargetStorageId] = useState<number | null>(null);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    
    // Fetch data on mount
    React.useEffect(() => {
        fetchStorageData();
    }, []);
    
    const fetchStorageData = async () => {
        try {
            const response = await fetch('/api/storage/grid-data/');
            if (!response.ok) throw new Error('Failed to load storage data');
            const json = await response.json();
            setData(json);
            setTargetStorageId(json.current_storage_id);
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
        
        // Don't allow drop on occupied cell (unless swapping is desired)
        if (targetCell.wine) {
            setMessage({ type: 'error', text: 'Cell is already occupied' });
            setDraggedCell(null);
            setDragOverCell(null);
            return;
        }
        
        try {
            const csrfToken = document.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]')?.value || '';
            
            const response = await fetch('/api/storage/move-bottle/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    item_id: draggedCell.wine.item_id,
                    target_storage_id: targetStorageId,
                    target_row: targetCell.row,
                    target_column: targetCell.column,
                }),
            });
            
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || 'Move failed');
            }
            
            // Refresh data
            await fetchStorageData();
            setMessage({ type: 'success', text: 'Bottle moved successfully' });
        } catch (e) {
            setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Move failed' });
        } finally {
            setDraggedCell(null);
            setDragOverCell(null);
        }
    }, [draggedCell, targetStorageId]);
    
    const handleMouseEnter = useCallback((wine: WineInfo, e: React.MouseEvent) => {
        setTooltip({ wine, position: { x: e.clientX, y: e.clientY } });
    }, []);
    
    const handleMouseLeave = useCallback(() => {
        setTooltip(null);
    }, []);
    
    const handleStorageChange = (storageId: number) => {
        setTargetStorageId(storageId);
    };
    
    // Clear message after 3 seconds
    React.useEffect(() => {
        if (message) {
            const timer = setTimeout(() => setMessage(null), 3000);
            return () => clearTimeout(timer);
        }
    }, [message]);
    
    if (loading) return <div className="storage-grid__loading">Loading...</div>;
    if (error) return <div className="storage-grid__error">Error: {error}</div>;
    if (!data) return <div className="storage-grid__empty">No storage data available</div>;
    
    const currentStorage = data.storages.find(s => s.id === targetStorageId);
    if (!currentStorage) return <div className="storage-grid__error">Storage not found</div>;
    
    // Build grid from storage dimensions
    const grid: CellData[][] = [];
    for (let row = 1; row <= currentStorage.rows; row++) {
        const rowCells: CellData[] = [];
        for (let col = 1; col <= currentStorage.columns; col++) {
            const item = currentStorage.items.find(i => i.row === row && i.column === col);
            rowCells.push({
                row,
                column: col,
                wine: item?.wine || null,
            });
        }
        grid.push(rowCells);
    }
    
    return (
        <div className="storage-grid">
            {/* Storage selector */}
            <div className="storage-grid__controls">
                <label htmlFor="storage-select">Storage:</label>
                <select
                    id="storage-select"
                    value={targetStorageId || ''}
                    onChange={(e) => handleStorageChange(Number(e.target.value))}
                    className="storage-grid__select"
                >
                    {data.storages.map(s => (
                        <option key={s.id} value={s.id}>
                            {s.name} ({s.rows}x{s.columns})
                        </option>
                    ))}
                </select>
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
                {Array.from({ length: currentStorage.columns }, (_, i) => (
                    <div key={i} className="storage-grid__col-label">{i + 1}</div>
                ))}
            </div>
            
            {/* Grid rows */}
            <div className="storage-grid__body">
                {grid.map((row, rowIdx) => (
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
                <p><i className="fa-solid fa-hand-pointer" /> Tap a bottle to see details</p>
                <p><i className="fa-solid fa-arrows-up-down-left-right" /> Drag and drop to move bottles</p>
            </div>
        </div>
    );
};

const initStorageGrid = () => {
    const container = document.getElementById('storage-grid-container');
    if (container) {
        // Get CSRF token from cookie or page
        const csrfInput = container.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]');
        const root = createRoot(container);
        root.render(<StorageGrid />);
    }
};

document.addEventListener('DOMContentLoaded', initStorageGrid, false);

export default StorageGrid;
