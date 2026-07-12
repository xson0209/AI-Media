/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ApiRequestOptions = {
  readonly method: 'GET' | 'PUT' | 'POST' | 'DELETE' | 'OPTIONS' | 'HEAD' | 'PATCH';
  readonly url: string;
  readonly path?: Record<string, unknown>;
  readonly cookies?: Record<string, unknown>;
  readonly headers?: Record<string, unknown>;
  readonly query?: Record<string, unknown>;
  readonly formData?: Record<string, unknown>;
  readonly body?: unknown;
  readonly mediaType?: string;
  readonly responseHeader?: string;
  readonly errors?: Record<number, string>;
};
