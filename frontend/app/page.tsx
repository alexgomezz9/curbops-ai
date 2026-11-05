'use client';
import dynamic from 'next/dynamic';
import { Suspense } from 'react';
const Dashboard = dynamic(() => import('@/components/dashboard'), { ssr: false, loading: () => <div className="loadingScreen"><span className="loadingGlyph">C/</span><span>INITIALIZING OPERATIONS WORKSPACE</span></div> });
export default function Home() {return <Suspense><Dashboard /></Suspense>;}
