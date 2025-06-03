import React from 'react';

function PaginationControls({ currentPage, totalPages, onPageChange }) {
    if (!totalPages || totalPages <= 1) return null;

    const handlePageClick = (pageNumber) => {
        if (pageNumber >= 1 && pageNumber <= totalPages) {
            onPageChange(pageNumber);
        }
    };

    // Simple display for brevity, you can make this more elaborate
    const pages = [];
    for(let i = 1; i <= totalPages; i++) {
        pages.push(i);
    }

    return (
        <div style={{ marginTop: '15px', textAlign: 'center' }}>
            <button onClick={() => handlePageClick(currentPage - 1)} disabled={currentPage === 1}>
                &laquo; Previous
            </button>
            <span style={{ margin: '0 10px' }}>
                Page {currentPage} of {totalPages}
            </span>
            <button onClick={() => handlePageClick(currentPage + 1)} disabled={currentPage === totalPages}>
                Next &raquo;
            </button>
            {/* Optional: Direct page jump input or more page numbers */}
        </div>
    );
}

export default PaginationControls;