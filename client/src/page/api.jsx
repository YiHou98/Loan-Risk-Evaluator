import axios from 'axios';


import {
  getRecordList,
  getPaginatedRecordList
} from '../graphql/queries';

import { authorizationHttpHeader } from '../utils';

import { getGraphQLEndpoint } from '../config';


export async function queryRecordList(type, record, config) {
    const result = [];
  
    return new Promise((resolve) => {
      axios.post(
        getGraphQLEndpoint('app'),
        {
          query: getRecordList,
          variables: {
            type,
            input: JSON.stringify(record)
          }
        },
        authorizationHttpHeader(config.authToken)
      ).then((response) => {
        if (response?.data?.data?.getRecordList) {
          resolve(response.data.data.getRecordList.map((item) => JSON.parse(item)));
        }
        resolve(result);
      }).catch(() => {
        resolve(result);
      });
    });
  }

  export async function queryPaginatedList(type, record, config) {
    return new Promise((resolve) => {
      axios.post(
        getGraphQLEndpoint('app'),
        {
          query: getPaginatedRecordList,
          variables: {
            type,
            input: JSON.stringify(record)
          }
        },
        authorizationHttpHeader(config.authToken)
      ).then((response) => {
        if (response?.data?.data?.getPaginatedRecordList) {
          const parsedResponse = JSON.parse(response.data.data.getPaginatedRecordList);
          resolve(parsedResponse);
        }
        resolve({ items: [], executionId: null, nextToken: null });
      }).catch(() => {
        resolve({ items: [], executionId: null, nextToken: null });
      });
    });
  }
  