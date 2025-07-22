import React from 'react';

function PaginationControls({ currentPage, totalPages, onPageChange }) {
    if (totalPages <= 1) {
        return null;
    }

    const handlePrevious = () => {
        if (currentPage > 1) {
            onPageChange(currentPage - 1);
        }
    };

    const handleNext = () => {
        if (currentPage < totalPages) {
            onPageChange(currentPage + 1);
        }
    };

    // Basic page number generation (can be made more sophisticated)
    const pageNumbers = [];
    const maxPagesToShow = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);

    if (totalPages > maxPagesToShow && endPage - startPage + 1 < maxPagesToShow) {
        startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        pageNumbers.push(i);
    }

    return (
        <div style={{ marginTop: '20px', textAlign: 'center' }}>
            <button onClick={handlePrevious} disabled={currentPage === 1} style={{ marginRight: '5px' }}>
                Previous
            </button>
            {startPage > 1 && (
                <>
                    <button onClick={() => onPageChange(1)} style={{ marginRight: '2px' }}>1</button>
                    {startPage > 2 && <span style={{ margin: '0 2px' }}>...</span>}
                </>
            )}
            {pageNumbers.map(number => (
                <button
                    key={number}
                    onClick={() => onPageChange(number)}
                    disabled={currentPage === number}
                    style={{ 
                        margin: '0 2px', 
                        fontWeight: currentPage === number ? 'bold' : 'normal' 
                    }}
                >
                    {number}
                </button>
            ))}
            {endPage < totalPages && (
                <>
                    {endPage < totalPages - 1 && <span style={{ margin: '0 2px' }}>...</span>}
                    <button onClick={() => onPageChange(totalPages)} style={{ marginLeft: '2px' }}>{totalPages}</button>
                </>
            )}
            <button onClick={handleNext} disabled={currentPage === totalPages} style={{ marginLeft: '5px' }}>
                Next
            </button>
        </div>
    );
}

export default PaginationControls;