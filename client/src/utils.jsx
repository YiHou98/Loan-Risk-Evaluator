export function authorizationHttpHeader(config) {
    return { headers: { 'x-api-key': config } };

};

export const getAuthConfig = () => {
    const apiKey = import.meta.env.VITE_APPSYNC_API_KEY;

    if (apiKey) {
        return {
            authToken: apiKey,
            authType: 'API_KEY'
        };
    } else {
        console.error(
            "AppSync API Key not found in environment variables. " +
            "Please set REACT_APP_APPSYNC_API_KEY (or VITE_APPSYNC_API_KEY) in your .env.local file and restart the dev server."
        );
        return {
            authToken: null,
            authType: 'NONE'
        };
    }
};

export const formatToMMDDHHMMSS = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    const pad = (num) => num.toString().padStart(2, '0');
    
    return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
           `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  };
  