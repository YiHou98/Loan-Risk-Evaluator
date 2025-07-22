import apiConfig from './api-config';

const appEnvironment = 'local';

export const getGraphQLEndpoint = (type) => {
  let endpoint = null;

  if (type === 'app') {
    endpoint = apiConfig[appEnvironment].appGraphQLEndpoint;
  } 
  return endpoint;
};