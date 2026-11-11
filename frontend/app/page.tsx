'use client';
import dynamic from 'next/dynamic';
import { Suspense } from 'react';
const Dashboard = dynamic(() => import('@/components/dashboard'), {
  ssr: false,
  loading: () => <div className="loadingScreen" role="status"><span className="v2LogoMark" aria-hidden="true">C.</span><span>Loading Madrid operations…</span></div>,
});
export default function Home() {return <Suspense><Dashboard /></Suspense>;}
