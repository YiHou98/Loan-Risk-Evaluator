export const getRecordList = /* GraphQL */ `
    query GetRecordList($type: String!, $input: AWSJSON!) {
      getRecordList(type: $type, input: $input)
    }
`;

export const getPaginatedRecordList = /* GraphQL */ `
    query GetPaginatedRecordList($type: String!, $input: AWSJSON!) {
      getPaginatedRecordList(type: $type, input: $input)
    }
`;