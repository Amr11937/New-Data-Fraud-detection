/**
 * Axios calls for Demask (subscriber ID recovery). Split out from api.ts
 * because these are multipart/form-data uploads with CSV blob responses,
 * a different shape from the rest of api.ts's typed JSON endpoints.
 */
import type { AxiosProgressEvent } from 'axios';
import api from './api';
import type { EncryptionMethodsResponse, ProcessingStats } from '@/types';

export interface DemaskResult {
  blob: Blob;
  filename: string;
  stats: ProcessingStats;
}

function statsFromHeaders(headers: Record<string, unknown>): ProcessingStats {
  return {
    total: Number(headers['x-total-records'] ?? 0),
    processed: Number(headers['x-processed'] ?? 0),
    unprocessed: Number(headers['x-unprocessed'] ?? 0),
    errors: Number(headers['x-errors'] ?? 0),
  };
}

export const runMapping = async (
  params: {
    inputFile: File;
    mappingFile: File;
    inputIdCol: string;
    mappingMaskedCol: string;
    mappingOriginalCol: string;
  },
  onUploadProgress?: (event: AxiosProgressEvent) => void
): Promise<DemaskResult> => {
  const fd = new FormData();
  fd.append('input_file', params.inputFile);
  fd.append('mapping_file', params.mappingFile);
  fd.append('input_id_col', params.inputIdCol);
  fd.append('mapping_masked_col', params.mappingMaskedCol);
  fd.append('mapping_original_col', params.mappingOriginalCol);

  const response = await api.post('/api/demask/mapping', fd, {
    responseType: 'blob',
    onUploadProgress,
  });

  return {
    blob: response.data,
    filename: 'updated_subscribers.csv',
    stats: statsFromHeaders(response.headers as Record<string, unknown>),
  };
};

export const fetchEncryptionMethods = async (): Promise<EncryptionMethodsResponse> => {
  const { data } = await api.get('/api/demask/encryption/methods');
  return data;
};

export const runEncryption = async (
  params: { inputFile: File; subscriberIdCol: string; encryptionMethod: string },
  onUploadProgress?: (event: AxiosProgressEvent) => void
): Promise<DemaskResult> => {
  const fd = new FormData();
  fd.append('input_file', params.inputFile);
  fd.append('subscriber_id_col', params.subscriberIdCol);
  fd.append('encryption_method', params.encryptionMethod);

  const response = await api.post('/api/demask/encryption', fd, {
    responseType: 'blob',
    onUploadProgress,
  });

  return {
    blob: response.data,
    filename: 'decrypted_subscribers.csv',
    stats: statsFromHeaders(response.headers as Record<string, unknown>),
  };
};
