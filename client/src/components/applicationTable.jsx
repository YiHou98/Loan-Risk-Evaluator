import React, { useState, useEffect, useCallback } from 'react';
import { queryPaginatedList } from '../page/api';
import PaginationControls from './paginationControls';
import { getAuthConfig, formatToMMDDHHMMSS} from '../utils';

const ApplicationRow = ({ app }) => (
    <tr>
        <td style={tableCellStyle}>{app.applicationId || 'N/A'}</td>
        <td style={tableCellStyle}>{app.loanAmount ? `$${app.loanAmount.toLocaleString()}` : 'N/A'}</td>
        <td style={tableCellStyle}>{app.term ? `${app.term} months` : 'N/A'}</td>
        <td style={tableCellStyle}>{app.riskLevel || 'N/A'}</td>
        <td style={tableCellStyle}>{app.riskScore ? app.riskScore.toFixed(4) : 'N/A'}</td>
        <td style={tableCellStyle}>{app.addressState || 'N/A'}</td>
        <td style={tableCellStyle}>{formatToMMDDHHMMSS(app.processingTimestamp)}</td>
    </tr>
);

function ApplicationsTable({ initialFilters = {}, onDataLoaded, itemsPerPage = 50 }) { // Changed default to 50
    const [allFetchedApps, setAllFetchedApps] = useState([]);
    const [displayedApps, setDisplayedApps] = useState([]);
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(0);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const loadAllData = useCallback((uiFilters) => {
        setIsLoading(true);
        setError(null);
        setAllFetchedApps([]);
        setDisplayedApps([]);
        setCurrentPage(1);
        setTotalPages(0);

        const authConfig = getAuthConfig();
        console.log('authConfig', authConfig);

        if (!authConfig || !authConfig.authToken || authConfig.authType === 'NONE' || authConfig.authType === 'API_KEY_ERROR') {
            setError("Authentication is not configured. Cannot fetch data.");
            setIsLoading(false);
            if (onDataLoaded) onDataLoaded(0);
            return;
        }

        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        const todayDateString = `${year}-${month}-${day}`;

        console.log("ApplicationsTable: Starting to fetch all records.");

        // Recursive function to fetch all pages
        const fetchAllPages = (accumulatedApps = [], currentOffset = 0, totalCountFromApi = null) => {
            const apiPageLimit = 1000; // API seems to limit to 100 per request
            
            const recordInputForApi = {
                ...uiFilters,
                startDate: uiFilters.startDate || todayDateString,
                endDate: uiFilters.endDate || todayDateString,
                limit: apiPageLimit,
                offset: currentOffset,
            };

            console.log(`Fetching with offset: ${currentOffset}, limit: ${apiPageLimit}`);
            
            queryPaginatedList("listApplication", recordInputForApi, authConfig)
                .then(response => {
                    console.log("API Response:", response);

                    if (response && Array.isArray(response.applications)) {
                        const newAccumulatedApps = [...accumulatedApps, ...response.applications];
                        
                        // Get total count on first request
                        if (currentOffset === 0 && response.totalCount !== undefined) {
                            totalCountFromApi = response.totalCount;
                            console.log("Total count from API:", totalCountFromApi);
                        }
                        
                        const newOffset = currentOffset + response.applications.length;
                        console.log(`Fetched ${response.applications.length} records, total so far: ${newOffset}`);

                        // Check if we need to fetch more
                        const hasMoreData = response.applications.length === apiPageLimit && 
                                          (totalCountFromApi === null || newOffset < totalCountFromApi);

                        if (hasMoreData) {
                            // Recursively fetch next page
                            fetchAllPages(newAccumulatedApps, newOffset, totalCountFromApi);
                        } else {
                            // All data fetched, update state
                            console.log(`Finished fetching. Total records: ${newAccumulatedApps.length}`);
                            setAllFetchedApps(newAccumulatedApps);
                            setTotalPages(Math.ceil(newAccumulatedApps.length / itemsPerPage));
                            setIsLoading(false);
                            
                            if (onDataLoaded) {
                                onDataLoaded(newAccumulatedApps.length);
                            }
                        }
                    } else {
                        console.warn("No applications in response or invalid structure:", response);
                        setAllFetchedApps(accumulatedApps);
                        setTotalPages(Math.ceil(accumulatedApps.length / itemsPerPage));
                        setIsLoading(false);
                        
                        if (onDataLoaded) {
                            onDataLoaded(accumulatedApps.length);
                        }
                    }
                })
                .catch(err => {
                    console.error("Error fetching page with offset", currentOffset, err);
                    setError(err.message || "Failed to fetch applications.");
                    setIsLoading(false);
                    
                    // Still show whatever we've fetched so far
                    if (accumulatedApps.length > 0) {
                        setAllFetchedApps(accumulatedApps);
                        setTotalPages(Math.ceil(accumulatedApps.length / itemsPerPage));
                    }
                    
                    if (onDataLoaded) {
                        onDataLoaded(accumulatedApps.length);
                    }
                });
        };

        // Start fetching from offset 0
        fetchAllPages();
        
    }, [itemsPerPage, onDataLoaded]);

    useEffect(() => {
        loadAllData(initialFilters);
    }, [initialFilters, loadAllData]);

    useEffect(() => {
        if (allFetchedApps.length > 0) {
            const startIndex = (currentPage - 1) * itemsPerPage;
            const endIndex = startIndex + itemsPerPage;
            setDisplayedApps(allFetchedApps.slice(startIndex, endIndex));
        } else {
            setDisplayedApps([]);
        }
    }, [allFetchedApps, currentPage, itemsPerPage]);

    const handlePageChange = (newPage) => {
        setCurrentPage(newPage);
    };

    if (isLoading) {
        return <div style={{ padding: '20px', textAlign: 'center' }}>Loading applications table...</div>;
    }

    if (error) {
        return <div style={{ padding: '20px', color: 'red', textAlign: 'center' }}>Error loading applications: {error}</div>;
    }

    return (
        <div style={containerStyle}>
            <div style={infoBarStyle}>
                <span>Total Applications: {allFetchedApps.length}</span>
                <span>Showing {displayedApps.length} records per page</span>
            </div>
            
            <div style={tableWrapperStyle}>
                <table style={tableStyle}>
                    <thead>
                        <tr>
                            <th style={tableHeaderStyle}>App ID</th>
                            <th style={tableHeaderStyle}>Loan Amount</th>
                            <th style={tableHeaderStyle}>Term</th>
                            <th style={tableHeaderStyle}>Risk Level</th>
                            <th style={tableHeaderStyle}>Risk Score</th>
                            <th style={tableHeaderStyle}>State</th>
                            <th style={tableHeaderStyle}>Processed Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayedApps.length > 0 ? (
                            displayedApps.map((app, index) => (
                               <ApplicationRow key={app.applicationId || `app-${index}`} app={app} />
                            ))
                        ) : (
                            <tr>
                                <td colSpan="8" style={{ textAlign: 'center', padding: '20px' }}>
                                    No applications to display for the selected criteria.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {allFetchedApps.length > 0 && totalPages > 1 && (
                <div style={paginationWrapperStyle}>
                    <PaginationControls
                        currentPage={currentPage}
                        totalPages={totalPages}
                        onPageChange={handlePageChange}
                    />
                </div>
            )}
        </div>
    );
}

// Styles
const containerStyle = {
    width: '100%',
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    overflow: 'hidden',
};

const infoBarStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '15px 20px',
    backgroundColor: '#f8f9fa',
    borderBottom: '1px solid #e9ecef',
    fontSize: '14px',
    color: '#495057',
};

const tableWrapperStyle = {
    maxHeight: '600px', // Make it scrollable
    overflowY: 'auto',
    overflowX: 'auto',
};

const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse',
    backgroundColor: '#ffffff',
};

const tableHeaderStyle = {
    position: 'sticky',
    top: 0,
    backgroundColor: '#343a40',
    color: '#ffffff',
    padding: '12px 15px',
    textAlign: 'left',
    fontWeight: '600',
    fontSize: '14px',
    borderBottom: '2px solid #dee2e6',
    whiteSpace: 'nowrap',
};

const tableCellStyle = {
    padding: '12px 15px',
    borderBottom: '1px solid #dee2e6',
    fontSize: '14px',
    color: '#212529',
};

const paginationWrapperStyle = {
    padding: '15px',
    borderTop: '1px solid #e9ecef',
    backgroundColor: '#f8f9fa',
};

export default ApplicationsTable;