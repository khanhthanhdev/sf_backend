# T2M Authentication & Session Flow Guide

## Overview

This guide covers the complete authentication and session management flow for the T2M (Text-to-Media) application using Clerk as the authentication provider. It includes frontend SDK setup, route protection, API token management, and secure file access patterns.

## Table of Contents

1. [Clerk Setup & Configuration](#clerk-setup--configuration)
2. [Frontend SDK Integration](#frontend-sdk-integration)
3. [Route Protection Strategy](#route-protection-strategy)
4. [API Token Management](#api-token-management)
5. [Secure File Access](#secure-file-access)
6. [Session Management](#session-management)
7. [Security Best Practices](#security-best-practices)
8. [Implementation Examples](#implementation-examples)

## Clerk Setup & Configuration

### 1. Clerk Dashboard Configuration

**Environment Setup:**
- **Development**: `https://dev.t2m-app.com`
- **Production**: `https://t2m-app.com`

**Required Clerk Settings:**
```javascript
// Environment Variables
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/onboarding
```

**Clerk Application Settings:**
- **Session token lifetime**: 7 days
- **JWT template**: Custom template for API integration
- **Allowed origins**: Your frontend domains
- **Webhook endpoints**: For user lifecycle events

### 2. JWT Template Configuration

Create a custom JWT template in Clerk dashboard:

```json
{
  "aud": "t2m-api",
  "exp": "{{session.expire_at}}",
  "iat": "{{session.created_at}}",
  "iss": "https://clerk.t2m-app.com",
  "sub": "{{user.id}}",
  "user_id": "{{user.id}}",
  "email": "{{user.primary_email_address.email_address}}",
  "role": "{{user.public_metadata.role}}",
  "permissions": "{{user.public_metadata.permissions}}",
  "subscription_tier": "{{user.public_metadata.subscription_tier}}"
}
```

## Frontend SDK Integration

### 1. Next.js Setup (@clerk/nextjs)

**Installation:**
```bash
npm install @clerk/nextjs
```

**App Router Configuration (app/layout.tsx):**
```typescript
import { ClerkProvider } from '@clerk/nextjs'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className={inter.className}>
          {children}
        </body>
      </html>
    </ClerkProvider>
  )
}
```

**Middleware Setup (middleware.ts):**
```typescript
import { authMiddleware } from "@clerk/nextjs";

export default authMiddleware({
  // Public routes that don't require authentication
  publicRoutes: [
    "/",
    "/api/auth/health",
    "/api/system/health",
    "/pricing",
    "/about",
    "/contact"
  ],
  
  // Routes that should be ignored by Clerk
  ignoredRoutes: [
    "/api/webhooks/clerk",
    "/api/files/secure/(.*)"  // Signed URL access
  ],
  
  // API routes that require authentication
  apiRoutes: ["/api/(.*)"],
  
  // Redirect after sign in
  afterAuth(auth, req, evt) {
    // Handle users who aren't authenticated
    if (!auth.userId && !auth.isPublicRoute) {
      return redirectToSignIn({ returnBackUrl: req.url });
    }
    
    // Redirect authenticated users away from public-only pages
    if (auth.userId && auth.isPublicRoute && req.nextUrl.pathname === "/") {
      const dashboard = new URL("/dashboard", req.url);
      return NextResponse.redirect(dashboard);
    }
  }
});

export const config = {
  matcher: ["/((?!.+\\.[\\w]+$|_next).*)", "/", "/(api|trpc)(.*)"],
};
```

### 2. React Components Setup

**Authentication Components:**
```typescript
// components/auth/SignInButton.tsx
import { SignInButton as ClerkSignInButton } from "@clerk/nextjs";

export function SignInButton() {
  return (
    <ClerkSignInButton mode="modal">
      <button className="btn-primary">
        Sign In
      </button>
    </ClerkSignInButton>
  );
}

// components/auth/UserButton.tsx
import { UserButton as ClerkUserButton } from "@clerk/nextjs";

export function UserButton() {
  return (
    <ClerkUserButton 
      afterSignOutUrl="/"
      appearance={{
        elements: {
          avatarBox: "w-8 h-8"
        }
      }}
    />
  );
}
```

**Protected Page Component:**
```typescript
// components/auth/ProtectedRoute.tsx
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
  requiredPermissions?: string[];
}

export function ProtectedRoute({ 
  children, 
  requiredRole,
  requiredPermissions 
}: ProtectedRouteProps) {
  const { isLoaded, isSignedIn, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push("/sign-in");
    }
  }, [isLoaded, isSignedIn, router]);

  if (!isLoaded) {
    return <LoadingSpinner />;
  }

  if (!isSignedIn) {
    return null;
  }

  // Check role-based access
  if (requiredRole) {
    const userRole = user?.publicMetadata?.role as string;
    if (userRole !== requiredRole) {
      return <div>Access denied. Required role: {requiredRole}</div>;
    }
  }

  // Check permission-based access
  if (requiredPermissions) {
    const userPermissions = user?.publicMetadata?.permissions as string[] || [];
    const hasPermission = requiredPermissions.every(permission => 
      userPermissions.includes(permission)
    );
    
    if (!hasPermission) {
      return <div>Access denied. Missing required permissions.</div>;
    }
  }

  return <>{children}</>;
}
```

## Route Protection Strategy

### 1. Public Routes (No Authentication Required)

```typescript
// Public routes configuration
const PUBLIC_ROUTES = [
  "/",                    // Landing page
  "/pricing",            // Pricing information
  "/about",              // About page
  "/contact",            // Contact page
  "/api/auth/health",    // Auth service health
  "/api/system/health",  // System health check
  "/legal/privacy",      // Privacy policy
  "/legal/terms"         // Terms of service
];
```

### 2. Protected Routes (Authentication Required)

```typescript
// Protected routes with different access levels
const PROTECTED_ROUTES = {
  // Basic authenticated routes
  AUTHENTICATED: [
    "/dashboard",
    "/profile",
    "/files",
    "/videos",
    "/jobs"
  ],
  
  // Admin-only routes
  ADMIN: [
    "/admin",
    "/admin/users",
    "/admin/system",
    "/admin/analytics"
  ],
  
  // Premium subscription routes
  PREMIUM: [
    "/premium/advanced-generation",
    "/premium/batch-processing",
    "/premium/priority-queue"
  ]
};
```

### 3. API Route Protection

```typescript
// app/api/auth/route-protection.ts
import { auth } from "@clerk/nextjs";
import { NextRequest, NextResponse } from "next/server";

export async function requireAuth(request: NextRequest) {
  const { userId } = auth();
  
  if (!userId) {
    return NextResponse.json(
      { error: "Unauthorized" }, 
      { status: 401 }
    );
  }
  
  return userId;
}

export async function requireRole(request: NextRequest, requiredRole: string) {
  const { userId, sessionClaims } = auth();
  
  if (!userId) {
    return NextResponse.json(
      { error: "Unauthorized" }, 
      { status: 401 }
    );
  }
  
  const userRole = sessionClaims?.metadata?.role as string;
  
  if (userRole !== requiredRole) {
    return NextResponse.json(
      { error: "Forbidden" }, 
      { status: 403 }
    );
  }
  
  return userId;
}

// Usage in API routes
// app/api/files/route.ts
import { requireAuth } from "@/app/api/auth/route-protection";

export async function GET(request: NextRequest) {
  const userId = await requireAuth(request);
  if (userId instanceof NextResponse) return userId; // Error response
  
  // Continue with authenticated logic
  // ...
}
```

## API Token Management

### 1. Token Retrieval in Frontend

```typescript
// hooks/useApiToken.ts
import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

export function useApiToken() {
  const { getToken } = useAuth();
  
  const getApiToken = useCallback(async () => {
    try {
      // Get token with custom JWT template
      const token = await getToken({ template: "t2m-api" });
      return token;
    } catch (error) {
      console.error("Failed to get API token:", error);
      throw new Error("Authentication failed");
    }
  }, [getToken]);
  
  return { getApiToken };
}

// Usage in components
function VideoUpload() {
  const { getApiToken } = useApiToken();
  
  const uploadVideo = async (file: File) => {
    const token = await getApiToken();
    
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/files/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });
    
    return response.json();
  };
  
  // ...
}
```

### 2. API Client with Automatic Token Management

```typescript
// lib/api-client.ts
import { useAuth } from "@clerk/nextjs";

class ApiClient {
  private baseUrl: string;
  private getToken: () => Promise<string | null>;
  
  constructor(baseUrl: string, getToken: () => Promise<string | null>) {
    this.baseUrl = baseUrl;
    this.getToken = getToken;
  }
  
  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const token = await this.getToken();
    
    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers,
      },
    };
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, config);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || 'API request failed');
    }
    
    return response.json();
  }
  
  // File operations
  async uploadFile(file: File, metadata?: any) {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      Object.entries(metadata).forEach(([key, value]) => {
        formData.append(key, value as string);
      });
    }
    
    const token = await this.getToken();
    return fetch(`${this.baseUrl}/files/upload`, {
      method: 'POST',
      headers: {
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: formData
    }).then(res => res.json());
  }
  
  async getFiles(params?: any) {
    const query = params ? `?${new URLSearchParams(params)}` : '';
    return this.request(`/files${query}`);
  }
  
  // Video operations
  async generateVideo(prompt: string, options?: any) {
    return this.request('/videos/generate', {
      method: 'POST',
      body: JSON.stringify({ prompt, ...options })
    });
  }
  
  async getJobStatus(jobId: string) {
    return this.request(`/jobs/${jobId}`);
  }
}

// Hook for using API client
export function useApiClient() {
  const { getToken } = useAuth();
  
  const apiClient = new ApiClient(
    process.env.NEXT_PUBLIC_API_URL || '/api/v1',
    () => getToken({ template: "t2m-api" })
  );
  
  return apiClient;
}
```

### 3. Backend Token Validation

```typescript
// Backend API token validation (if using proxy)
// app/api/auth/validate-token.ts
import { verifyToken } from "@clerk/backend";

export async function validateClerkToken(token: string) {
  try {
    const payload = await verifyToken(token, {
      jwtKey: process.env.CLERK_JWT_KEY,
      authorizedParties: [process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY]
    });
    
    return {
      userId: payload.sub,
      email: payload.email,
      role: payload.role,
      permissions: payload.permissions,
      subscriptionTier: payload.subscription_tier
    };
  } catch (error) {
    throw new Error('Invalid token');
  }
}

// Usage in API routes
export async function POST(request: NextRequest) {
  const authHeader = request.headers.get('authorization');
  const token = authHeader?.replace('Bearer ', '');
  
  if (!token) {
    return NextResponse.json({ error: 'No token provided' }, { status: 401 });
  }
  
  try {
    const user = await validateClerkToken(token);
    // Continue with authenticated logic
  } catch (error) {
    return NextResponse.json({ error: 'Invalid token' }, { status: 401 });
  }
}
```

## Secure File Access

### 1. Signed URL Generation

```typescript
// Backend: Generate signed URLs for secure file access
// app/api/files/[fileId]/signed-url/route.ts
import { auth } from "@clerk/nextjs";
import { createHmac } from "crypto";

export async function POST(
  request: NextRequest,
  { params }: { params: { fileId: string } }
) {
  const { userId } = auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  
  const { fileId } = params;
  const { expiresIn = 3600 } = await request.json(); // Default 1 hour
  
  // Verify user owns the file
  const file = await getFileById(fileId);
  if (!file || file.userId !== userId) {
    return NextResponse.json({ error: "File not found" }, { status: 404 });
  }
  
  // Generate signed URL
  const expires = Math.floor(Date.now() / 1000) + expiresIn;
  const signature = createHmac('sha256', process.env.FILE_SIGNING_SECRET!)
    .update(`${fileId}:${userId}:${expires}`)
    .digest('hex');
  
  const signedUrl = `${process.env.NEXT_PUBLIC_API_URL}/files/secure/${fileId}?` +
    `user_id=${userId}&expires=${expires}&signature=${signature}`;
  
  return NextResponse.json({
    success: true,
    data: {
      url: signedUrl,
      expires_at: new Date(expires * 1000).toISOString()
    }
  });
}
```

### 2. Signed URL Validation

```typescript
// Backend: Validate signed URLs
// app/api/files/secure/[fileId]/route.ts
import { createHmac } from "crypto";
import { NextRequest, NextResponse } from "next/server";

export async function GET(
  request: NextRequest,
  { params }: { params: { fileId: string } }
) {
  const { fileId } = params;
  const { searchParams } = new URL(request.url);
  
  const userId = searchParams.get('user_id');
  const expires = searchParams.get('expires');
  const signature = searchParams.get('signature');
  
  if (!userId || !expires || !signature) {
    return NextResponse.json({ error: "Invalid signed URL" }, { status: 400 });
  }
  
  // Check expiration
  const expiresTimestamp = parseInt(expires);
  if (Date.now() / 1000 > expiresTimestamp) {
    return NextResponse.json({ error: "Signed URL expired" }, { status: 410 });
  }
  
  // Verify signature
  const expectedSignature = createHmac('sha256', process.env.FILE_SIGNING_SECRET!)
    .update(`${fileId}:${userId}:${expires}`)
    .digest('hex');
  
  if (signature !== expectedSignature) {
    return NextResponse.json({ error: "Invalid signature" }, { status: 403 });
  }
  
  // Serve file
  const file = await getFileById(fileId);
  if (!file || file.userId !== userId) {
    return NextResponse.json({ error: "File not found" }, { status: 404 });
  }
  
  // Return file stream
  const fileStream = await getFileStream(file.path);
  return new NextResponse(fileStream, {
    headers: {
      'Content-Type': file.contentType,
      'Content-Disposition': `attachment; filename="${file.filename}"`,
      'Cache-Control': 'private, max-age=3600'
    }
  });
}
```

### 3. Frontend: Secure Video Player

```typescript
// components/VideoPlayer.tsx
import { useApiClient } from "@/lib/api-client";
import { useEffect, useState } from "react";

interface VideoPlayerProps {
  jobId: string;
  autoplay?: boolean;
}

export function VideoPlayer({ jobId, autoplay = false }: VideoPlayerProps) {
  const [signedUrl, setSignedUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const apiClient = useApiClient();
  
  useEffect(() => {
    async function getSignedUrl() {
      try {
        setLoading(true);
        
        // Get signed URL for video
        const response = await apiClient.request(`/videos/${jobId}/signed-url`, {
          method: 'POST',
          body: JSON.stringify({ expiresIn: 3600 }) // 1 hour
        });
        
        setSignedUrl(response.data.url);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load video');
      } finally {
        setLoading(false);
      }
    }
    
    getSignedUrl();
  }, [jobId, apiClient]);
  
  if (loading) return <div>Loading video...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!signedUrl) return <div>Video not available</div>;
  
  return (
    <video
      src={signedUrl}
      controls
      autoPlay={autoplay}
      className="w-full h-auto rounded-lg"
      onError={() => setError('Failed to load video')}
    >
      Your browser does not support the video tag.
    </video>
  );
}
```

## Session Management

### 1. Session Configuration

```typescript
// lib/session-config.ts
export const SESSION_CONFIG = {
  // Session duration
  maxAge: 7 * 24 * 60 * 60, // 7 days in seconds
  
  // Token refresh threshold
  refreshThreshold: 5 * 60, // Refresh if expires in 5 minutes
  
  // Automatic logout on inactivity
  inactivityTimeout: 30 * 60, // 30 minutes
  
  // Remember me option
  rememberMe: {
    enabled: true,
    duration: 30 * 24 * 60 * 60 // 30 days
  }
};
```

### 2. Session Monitoring Hook

```typescript
// hooks/useSessionMonitor.ts
import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef } from "react";

export function useSessionMonitor() {
  const { isSignedIn, signOut } = useAuth();
  const lastActivityRef = useRef(Date.now());
  const inactivityTimerRef = useRef<NodeJS.Timeout>();
  
  const resetInactivityTimer = () => {
    lastActivityRef.current = Date.now();
    
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
    }
    
    inactivityTimerRef.current = setTimeout(() => {
      if (isSignedIn) {
        signOut();
        alert('You have been logged out due to inactivity.');
      }
    }, SESSION_CONFIG.inactivityTimeout * 1000);
  };
  
  useEffect(() => {
    if (!isSignedIn) return;
    
    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
    
    events.forEach(event => {
      document.addEventListener(event, resetInactivityTimer, true);
    });
    
    resetInactivityTimer(); // Initialize timer
    
    return () => {
      events.forEach(event => {
        document.removeEventListener(event, resetInactivityTimer, true);
      });
      
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
      }
    };
  }, [isSignedIn]);
}
```

### 3. Token Refresh Management

```typescript
// hooks/useTokenRefresh.ts
import { useAuth } from "@clerk/nextjs";
import { useEffect, useCallback } from "react";

export function useTokenRefresh() {
  const { getToken, isSignedIn } = useAuth();
  
  const checkTokenExpiry = useCallback(async () => {
    if (!isSignedIn) return;
    
    try {
      const token = await getToken({ template: "t2m-api" });
      if (!token) return;
      
      // Decode JWT to check expiry
      const payload = JSON.parse(atob(token.split('.')[1]));
      const expiryTime = payload.exp * 1000; // Convert to milliseconds
      const currentTime = Date.now();
      const timeUntilExpiry = expiryTime - currentTime;
      
      // Refresh if token expires within threshold
      if (timeUntilExpiry < SESSION_CONFIG.refreshThreshold * 1000) {
        await getToken({ template: "t2m-api", skipCache: true });
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
    }
  }, [getToken, isSignedIn]);
  
  useEffect(() => {
    if (!isSignedIn) return;
    
    // Check token expiry every minute
    const interval = setInterval(checkTokenExpiry, 60 * 1000);
    
    return () => clearInterval(interval);
  }, [isSignedIn, checkTokenExpiry]);
}
```

## Security Best Practices

### 1. Token Security

```typescript
// Security guidelines for token handling

// ✅ DO: Use secure token storage
const { getToken } = useAuth();
const token = await getToken({ template: "t2m-api" });

// ❌ DON'T: Store tokens in localStorage or sessionStorage
localStorage.setItem('token', token); // NEVER DO THIS

// ✅ DO: Use tokens for API calls only
const response = await fetch('/api/files', {
  headers: { 'Authorization': `Bearer ${token}` }
});

// ❌ DON'T: Embed tokens in URLs or HTML
const videoUrl = `/video?token=${token}`; // NEVER DO THIS
```

### 2. CSRF Protection

```typescript
// middleware.ts - CSRF protection
import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  // CSRF protection for state-changing operations
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(request.method)) {
    const origin = request.headers.get('origin');
    const host = request.headers.get('host');
    
    if (origin && !origin.includes(host!)) {
      return NextResponse.json(
        { error: 'CSRF protection: Invalid origin' },
        { status: 403 }
      );
    }
  }
  
  return NextResponse.next();
}
```

### 3. Rate Limiting

```typescript
// lib/rate-limiter.ts
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

export const rateLimiter = new Ratelimit({
  redis,
  limiter: Ratelimit.slidingWindow(100, "1 h"), // 100 requests per hour
  analytics: true,
});

// Usage in API routes
export async function POST(request: NextRequest) {
  const { userId } = auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  
  const { success, limit, reset, remaining } = await rateLimiter.limit(userId);
  
  if (!success) {
    return NextResponse.json(
      { error: "Rate limit exceeded" },
      { 
        status: 429,
        headers: {
          'X-RateLimit-Limit': limit.toString(),
          'X-RateLimit-Remaining': remaining.toString(),
          'X-RateLimit-Reset': reset.toString(),
        }
      }
    );
  }
  
  // Continue with request processing
}
```

## Implementation Examples

### 1. Complete Authentication Flow

```typescript
// app/dashboard/page.tsx
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useSessionMonitor } from "@/hooks/useSessionMonitor";
import { useTokenRefresh } from "@/hooks/useTokenRefresh";

export default function DashboardPage() {
  useSessionMonitor(); // Monitor for inactivity
  useTokenRefresh();   // Handle token refresh
  
  return (
    <ProtectedRoute>
      <div className="dashboard">
        <h1>Welcome to T2M Dashboard</h1>
        {/* Dashboard content */}
      </div>
    </ProtectedRoute>
  );
}
```

### 2. File Upload with Progress

```typescript
// components/FileUpload.tsx
import { useApiClient } from "@/lib/api-client";
import { useState } from "react";

export function FileUpload() {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const apiClient = useApiClient();
  
  const handleUpload = async (file: File) => {
    setUploading(true);
    setProgress(0);
    
    try {
      // Create XMLHttpRequest for progress tracking
      const formData = new FormData();
      formData.append('file', file);
      
      const token = await apiClient.getApiToken();
      
      const xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          setProgress((e.loaded / e.total) * 100);
        }
      });
      
      xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
          const response = JSON.parse(xhr.responseText);
          console.log('Upload successful:', response);
        }
      });
      
      xhr.open('POST', '/api/files/upload');
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.send(formData);
      
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  };
  
  return (
    <div className="file-upload">
      <input
        type="file"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleUpload(file);
        }}
        disabled={uploading}
      />
      
      {uploading && (
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${progress}%` }}
          />
          <span>{Math.round(progress)}%</span>
        </div>
      )}
    </div>
  );
}
```

### 3. Video Generation with Real-time Updates

```typescript
// components/VideoGenerator.tsx
import { useApiClient } from "@/lib/api-client";
import { useState, useEffect } from "react";

export function VideoGenerator() {
  const [prompt, setPrompt] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [progress, setProgress] = useState(0);
  const apiClient = useApiClient();
  
  const generateVideo = async () => {
    try {
      setStatus("starting");
      
      const response = await apiClient.generateVideo(prompt, {
        duration: 10,
        quality: "1080p"
      });
      
      setJobId(response.data.job_id);
      setStatus("processing");
    } catch (error) {
      console.error('Video generation failed:', error);
      setStatus("error");
    }
  };
  
  // Poll for job status
  useEffect(() => {
    if (!jobId || status === "completed" || status === "error") return;
    
    const pollStatus = async () => {
      try {
        const response = await apiClient.getJobStatus(jobId);
        setStatus(response.data.status);
        setProgress(response.data.progress || 0);
      } catch (error) {
        console.error('Status check failed:', error);
      }
    };
    
    const interval = setInterval(pollStatus, 2000); // Poll every 2 seconds
    return () => clearInterval(interval);
  }, [jobId, status, apiClient]);
  
  return (
    <div className="video-generator">
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe your video..."
        disabled={status === "processing"}
      />
      
      <button 
        onClick={generateVideo}
        disabled={!prompt || status === "processing"}
      >
        {status === "processing" ? "Generating..." : "Generate Video"}
      </button>
      
      {status === "processing" && (
        <div className="status">
          <div className="progress-bar">
            <div style={{ width: `${progress}%` }} />
          </div>
          <p>Progress: {progress}%</p>
        </div>
      )}
      
      {status === "completed" && jobId && (
        <VideoPlayer jobId={jobId} />
      )}
    </div>
  );
}
```

## Troubleshooting

### Common Issues

1. **Token Expiry**: Implement automatic token refresh
2. **CORS Issues**: Configure Clerk allowed origins properly
3. **Webhook Failures**: Verify webhook URL accessibility
4. **Rate Limiting**: Implement proper rate limiting and user feedback

### Debug Tools

```typescript
// Debug helper for authentication issues
export function useAuthDebug() {
  const { isLoaded, isSignedIn, user, getToken } = useAuth();
  
  const debugAuth = async () => {
    console.log('Auth Debug Info:', {
      isLoaded,
      isSignedIn,
      userId: user?.id,
      email: user?.primaryEmailAddress?.emailAddress,
      metadata: user?.publicMetadata
    });
    
    if (isSignedIn) {
      try {
        const token = await getToken({ template: "t2m-api" });
        console.log('Token:', token);
        
        if (token) {
          const payload = JSON.parse(atob(token.split('.')[1]));
          console.log('Token payload:', payload);
        }
      } catch (error) {
        console.error('Token error:', error);
      }
    }
  };
  
  return { debugAuth };
}
```

This comprehensive guide covers all aspects of authentication and session management for the T2M application, ensuring secure and efficient user experience while maintaining best practices for token handling and file access.