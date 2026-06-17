import type { ApiError, ApiClientOptions } from "./types";
import { getApiUrl, isConfigReady } from "../config";

class ApiClient {
  private tokenKey: string;

  constructor(options: ApiClientOptions = {}) {
    this.tokenKey = options.tokenKey ?? "grid_token";
  }

  getBaseUrl(): string {
    if (isConfigReady()) {
      try {
        return getApiUrl();
      } catch {
        return window.location.origin;
      }
    }
    return window.location.origin;
  }

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  setToken(token: string | null): void {
    if (token) {
      localStorage.setItem(this.tokenKey, token);
    } else {
      localStorage.removeItem(this.tokenKey);
    }
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const baseUrl = this.getBaseUrl();
    const headers = new Headers({
      "Content-Type": "application/json",
    });

    const token = this.getToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    if (options.headers) {
      const existingHeaders = new Headers(options.headers);
      existingHeaders.forEach((value, key) => headers.set(key, value));
    }

    const response = await fetch(`${baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let message: string;
      try {
        const body = (await response.json()) as ApiError;
        message = body.error ?? response.statusText;
      } catch {
        message = response.statusText || `HTTP ${response.status}`;
      }
      const errorMsg =
        response.status >= 500
          ? `Server error: ${message}`
          : `Request failed: ${message}`;
      throw Object.assign(new Error(errorMsg), {
        status: response.status,
        endpoint,
      });
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "GET" });
  }

  async post<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE" });
  }

  async patch<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}

export const api = new ApiClient();
export { ApiClient };
