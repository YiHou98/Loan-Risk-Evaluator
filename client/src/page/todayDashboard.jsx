import React, { useState, memo} from 'react';
import CountGraph from '../components/countGraph';
import RiskGraph from '../components/riskGraph';
import ApplicationsTable from '../components/applicationTable';
import PaginationControls from '../components/paginationControls';

const GraphsSection = memo(() => {
    const today = new Date();
    const todayDateString = today.toISOString().split('T')[0];
    
    const graphFilters = {
        startDate: todayDateString,
        endDate: todayDateString,
    };

    return (
        <div style={graphContainerStyle}>
            <div style={graphBoxStyle}>
                <CountGraph filters={graphFilters} />
            </div>
            <div style={graphBoxStyle}>
                <RiskGraph filters={graphFilters} />
            </div>
        </div>
    );
});

const DashboardFilters = ({ onFilterSubmit }) => {
    const [riskLevel, setRiskLevel] = useState('');
    const [addrState, setAddrState] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        onFilterSubmit({ riskLevel: riskLevel || undefined, addressState: addrState || undefined });
    };

    return (
        <form onSubmit={handleSubmit} style={filterFormStyle}>
            <label htmlFor="riskLevelFilter" style={labelStyle}>Risk Level: </label>
            <select 
                id="riskLevelFilter"
                value={riskLevel} 
                onChange={(e) => setRiskLevel(e.target.value)}
                style={selectStyle}
            >
                <option value="">All</option>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
            </select>
            
            <label htmlFor="stateFilter" style={labelStyle}>State: </label>
            <input 
                id="stateFilter"
                type="text" 
                value={addrState} 
                onChange={(e) => setAddrState(e.target.value.toUpperCase())} 
                placeholder="e.g., CA"
                maxLength={2}
                style={inputStyle}
            />
            
            <button type="submit" style={buttonStyle}>Apply Filters</button>
        </form>
    );
};

function TodaysDashboardPage() {
    const [dashboardFilters, setDashboardFilters] = useState({});
    const [totalAppsInTable, setTotalAppsInTable] = useState(0);

    const handleDashboardFilterSubmission = (submittedFilters) => {
        setDashboardFilters(submittedFilters);
    };
    
    const handleTableDataLoaded = (count) => {
        setTotalAppsInTable(count);
    };

    return (
        <div style={pageContainerStyle}>
            <h1 style={pageTitleStyle}>Today's Loan Application Dashboard</h1>
            
            <GraphsSection />

            <div style={tableContainerStyle}>
                <h2 style={sectionTitleStyle}>Applications Overview (Today)</h2>
                <p style={subtitleStyle}>Total applications shown in table: {totalAppsInTable}</p>
                
                {/* Filter bar moved here - under title but above table */}
                <DashboardFilters onFilterSubmit={handleDashboardFilterSubmission} />
                
                <ApplicationsTable 
                    initialFilters={dashboardFilters} 
                    onDataLoaded={handleTableDataLoaded}
                    itemsPerPage={50} // Increased from 10 to 50
                />
            </div>
        </div>
    );
}

// Styles
const pageContainerStyle = {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    margin: '0',
    padding: '20px',
    backgroundColor: '#f5f5f5',
    minHeight: '100vh',
};

const pageTitleStyle = {
    color: '#1a1a1a',
    fontSize: '28px',
    fontWeight: '600',
    marginBottom: '30px',
    textAlign: 'center',
};

const graphContainerStyle = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '20px',
    marginBottom: '30px',
};

const graphBoxStyle = {
    flex: '1 1 45%',
    minWidth: '300px',
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    padding: '20px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
};

const tableContainerStyle = {
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    padding: '20px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
};

const sectionTitleStyle = {
    color: '#333333',
    fontSize: '22px',
    fontWeight: '600',
    marginTop: '0',
    marginBottom: '10px',
};

const subtitleStyle = {
    color: '#666666',
    fontSize: '16px',
    marginBottom: '20px',
};

const filterFormStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '15px',
    padding: '15px',
    backgroundColor: '#f8f9fa',
    borderRadius: '6px',
    marginBottom: '20px',
    flexWrap: 'wrap',
};

const labelStyle = {
    fontSize: '14px',
    fontWeight: '500',
    color: '#495057',
};

const selectStyle = {
    padding: '8px 12px',
    borderRadius: '4px',
    border: '1px solid #ced4da',
    fontSize: '14px',
    minWidth: '120px',
};

const inputStyle = {
    padding: '8px 12px',
    borderRadius: '4px',
    border: '1px solid #ced4da',
    fontSize: '14px',
    width: '80px',
    textTransform: 'uppercase',
};

const buttonStyle = {
    padding: '8px 20px',
    borderRadius: '4px',
    border: 'none',
    backgroundColor: '#007bff',
    color: '#ffffff',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'background-color 0.2s',
};

export default TodaysDashboardPage;