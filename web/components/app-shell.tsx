'use client';

import Link from 'next/link';
import { BookOpen, ChevronDown, FileImage, FileText, LogOut, Menu, RotateCcw, UserRound, X } from 'lucide-react';
import { ReactNode, useEffect, useState } from 'react';

const primaryLinks = [
  { href: '/gear', label: 'Browse gear', id: 'gear' },
  { href: '/borrowing', label: 'Borrowing', id: 'borrowing' },
  { href: '/returns', label: 'Returns', id: 'returns' },
];

const lenderLinks = [
  { href: '/photos', label: 'Item photos', description: 'Prepare listing images', icon: FileImage, id: 'photos' },
  { href: '/manuals', label: 'Manual viewer', description: 'Check a kit manual', icon: FileText, id: 'manuals' },
];

export function AppShell({ active, children }: { active: string; children: ReactNode }) {
  const [resetState, setResetState] = useState<'idle' | 'resetting' | 'error'>('idle');
  const [gatewayTeam, setGatewayTeam] = useState<string | null>(null);
  const [briefOpen, setBriefOpen] = useState(false);

  useEffect(() => {
    fetch('/auth/session')
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => {
        const team = typeof payload?.team === 'string' && /^team\d{2}$/.test(payload.team) ? payload.team : null;
        setGatewayTeam(team);
        if (sessionStorage.getItem(`bfc-brief-seen:${team || 'local'}`) !== '1') setBriefOpen(true);
      })
      .catch(() => {
        if (sessionStorage.getItem('bfc-brief-seen:local') !== '1') setBriefOpen(true);
      });
  }, []);

  function dismissBrief() {
    sessionStorage.setItem(`bfc-brief-seen:${gatewayTeam || 'local'}`, '1');
    setBriefOpen(false);
  }

  async function resetLocalLab() {
    if (!window.confirm('Reset this practice environment? Saved condition reports will be deleted.')) return;
    setResetState('resetting');
    try {
      const response = await fetch('/api/workspace/reset', { method: 'POST' });
      if (!response.ok) throw new Error('Reset failed');
      window.location.reload();
    } catch {
      setResetState('error');
    }
  }

  const practiceActions = (
    <>
      <button type="button" aria-label="Assignment brief" onClick={() => setBriefOpen(true)}><BookOpen size={17} />Assignment brief</button>
      <button type="button" aria-label="Reset practice environment" onClick={resetLocalLab} disabled={resetState === 'resetting'}><RotateCcw size={17} />{resetState === 'resetting' ? 'Resetting...' : 'Reset practice environment'}</button>
      {gatewayTeam && <form method="post" action="/logout" onSubmit={() => sessionStorage.removeItem(`bfc-brief-seen:${gatewayTeam}`)}><button type="submit" aria-label="Sign out"><LogOut size={17} />Sign out</button></form>}
      {resetState === 'error' && <p role="alert">Reset failed. Try again.</p>}
    </>
  );

  return (
    <div className="site-frame">
      <header className="site-header">
        <div className="site-header-inner">
          <Link className="site-brand" href="/gear" aria-label="Relay CCS-KU BFC home"><span className="brand-symbol" aria-hidden="true">R</span><span>relay</span><span className="site-course-badge">CCS-KU BFC</span></Link>
          <nav className="site-primary-nav" aria-label="Main navigation">
            {primaryLinks.map((item) => <Link key={item.id} href={item.href} aria-current={active === item.id ? 'page' : undefined}>{item.label}</Link>)}
            <details className="site-lender-menu" name="header-menu">
              <summary className={lenderLinks.some((item) => item.id === active) ? 'active' : ''}>For lenders <ChevronDown size={15} /></summary>
              <div className="site-menu-panel lender-menu-panel">
                {lenderLinks.map((item) => { const Icon = item.icon; return <Link key={item.id} href={item.href} aria-label={item.label} aria-current={active === item.id ? 'page' : undefined}><Icon size={18} /><span><strong>{item.label}</strong><small>{item.description}</small></span></Link>; })}
              </div>
            </details>
          </nav>
          <div className="site-header-actions">
            <details className="site-account-menu" name="header-menu">
              <summary aria-label="Practice menu"><UserRound size={17} /><span>{gatewayTeam || 'Local practice'}</span><ChevronDown size={14} /></summary>
              <div className="site-menu-panel practice-menu-panel">{practiceActions}</div>
            </details>
            <details className="site-mobile-menu">
              <summary aria-label="Open navigation"><Menu size={22} /></summary>
              <nav className="site-mobile-panel" aria-label="Mobile navigation">
                {primaryLinks.map((item) => <Link key={item.id} href={item.href} aria-label={item.label} aria-current={active === item.id ? 'page' : undefined}>{item.label}</Link>)}
                <span className="site-mobile-label">For lenders</span>
                {lenderLinks.map((item) => <Link key={item.id} href={item.href} aria-label={item.label} aria-current={active === item.id ? 'page' : undefined}>{item.label}</Link>)}
                <div className="site-mobile-actions">{practiceActions}</div>
              </nav>
            </details>
          </div>
        </div>
      </header>
      <main className="site-main">{children}</main>
      <footer className="site-footer"><div><Link className="site-footer-brand" href="/gear">relay</Link><span>Shared gear, ready when you are.</span><span className="site-footer-course">CCS-KU BFC · Korea University course security practice</span><nav aria-label="Footer navigation"><Link href="/borrowing?file=pickup-guide.txt">Pickup guide</Link><Link href="/returns">Returns</Link></nav></div></footer>
      {briefOpen && <div className="brief-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) dismissBrief(); }}><section className="assignment-brief" role="dialog" aria-modal="true" aria-labelledby="brief-title"><div className="brief-head"><span>RELAY / GEAR LIBRARY</span><button type="button" onClick={dismissBrief} aria-label="Close assignment brief"><X size={18} /></button></div><div className="brief-content"><p className="brief-eyebrow">BUG FINDING CHALLENGE</p><h2 id="brief-title">The lending desk is yours to explore.</h2><p>Relay helps people find shared gear, prepare loan documents, record returns, and preview photos and manuals. Your team is assessing this working service before wider use.</p><div className="brief-task"><strong>Explore the workflows. Verify the impact.</strong><span>Use the running site and supplied source to investigate unexpected behavior. Compare it with a normal request, reproduce your finding in your assigned practice environment, and submit a report with evidence.</span></div><p className="brief-fineprint">All five areas are ordinary product features. They do not describe where a vulnerability is located.</p></div><div className="brief-footer"><button className="primary-button" type="button" onClick={dismissBrief}>Explore Relay</button></div></section></div>}
    </div>
  );
}
