'use client';

import Link from 'next/link';
import { ArrowUpRight, FileArchive, FileDown, FileImage, FileText, FolderOpen, MessageSquareText, Save, Search, Send, Trash2, UserRoundCheck } from 'lucide-react';
import { FormEvent, useEffect, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { ConditionReportBody } from '@/components/condition-report-body';

type Track = 'gear' | 'borrowing' | 'returns';
type SearchRow = { id: number; title: string; summary: string; owner: string; visibility: string };
type Note = { id: string; body: string; createdAt: string };
type ReturnApproval = { id: string; noteId: string; approvedAt: string; verificationCode?: string };
type PickupBundle = { jobId: string; name: string; status: 'saved' | 'ready' | 'failed'; documents: string[]; createdAt: string };

const bundleDocumentOptions = [
  { id: 'pickup', label: 'Pickup sheet' },
  { id: 'equipment', label: 'Equipment list' },
  { id: 'handover', label: 'Handover instructions' },
];

const trackInfo: Record<Track, { title: string; subtitle: string }> = {
  gear: { title: 'Find your next kit.', subtitle: 'Browse shared gear and prepare a saved selection for the lending desk.' },
  borrowing: { title: 'Loan documents', subtitle: 'Pickup guidance and care instructions that travel with every booking.' },
  returns: { title: 'Condition reports', subtitle: 'Record a return, then send the queue to staff for review.' },
};

const publicFiles = ['kit-index.json', 'pickup-guide.txt', 'care-sheet.txt'];

export function RelayWorkspace({ track = 'gear' }: { track?: Track }) {
  const [query, setQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [rows, setRows] = useState<SearchRow[]>([]);
  const [exportRows, setExportRows] = useState<SearchRow[] | null>(null);
  const [savedViewId, setSavedViewId] = useState<string | null>(null);
  const [bundleName, setBundleName] = useState('');
  const [bundleDocuments, setBundleDocuments] = useState<string[]>(['pickup', 'equipment']);
  const [bundle, setBundle] = useState<PickupBundle | null>(null);
  const [bundleError, setBundleError] = useState('');
  const [searchError, setSearchError] = useState('');
  const [artifactPath, setArtifactPath] = useState('');
  const [artifactOutput, setArtifactOutput] = useState('');
  const [artifactError, setArtifactError] = useState('');
  const [noteBody, setNoteBody] = useState('');
  const [notes, setNotes] = useState<Note[]>([]);
  const [approvals, setApprovals] = useState<ReturnApproval[]>([]);
  const [noteError, setNoteError] = useState('');
  const [reviewAvailable, setReviewAvailable] = useState(false);
  const [reviewMessage, setReviewMessage] = useState('');
  const [staffView, setStaffView] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  async function loadRows(term: string) {
    const response = await fetch(`/api/gear/search?q=${encodeURIComponent(term)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Inventory could not be searched.');
    setRows(payload.rows || []);
    setActiveFilter(term);
    setSavedViewId(null);
    setExportRows(null);
    setBundle(null);
    setBundleError('');
  }

  async function loadNotes() {
    const response = await fetch('/api/returns/reports');
    const payload = await response.json();
    setNotes(payload.notes || []);
  }

  async function loadApprovals() {
    const response = await fetch('/api/returns/approvals');
    const payload = await response.json();
    const items = (payload.approvals || []) as ReturnApproval[];
    setApprovals(items);
    return items;
  }

  useEffect(() => {
    if (track !== 'gear') return;
    const initialQuery = new URLSearchParams(window.location.search).get('search') || '';
    setQuery(initialQuery);
    loadRows(initialQuery).catch(() => setSearchError('Inventory is temporarily unavailable.'));
  }, [track]);

  useEffect(() => {
    if (track !== 'borrowing') return;
    const file = new URLSearchParams(window.location.search).get('file');
    if (file && publicFiles.includes(file)) void openArtifact(file);
  }, [track]);

  useEffect(() => {
    if (track !== 'returns') return;
    setStaffView(false);
    if (new URLSearchParams(window.location.search).get('staff') === '1') {
      fetch('/api/returns/review/context')
        .then((response) => response.json())
        .then((payload) => setStaffView(payload.staff === true))
        .catch(() => setStaffView(false));
    }
    loadNotes().catch(() => setNoteError('Condition reports could not be loaded.'));
    loadApprovals().catch(() => setNoteError('Return approvals could not be loaded.'));
    fetch('/api/returns/review/status')
      .then((response) => response.json())
      .then((payload) => setReviewAvailable(payload.available === true))
      .catch(() => setReviewAvailable(false));
  }, [track]);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy('search');
    setSearchError('');
    try { await loadRows(query); }
    catch (error) { setSearchError(error instanceof Error ? error.message : 'Inventory could not be searched.'); }
    finally { setBusy(null); }
  }

  async function saveView() {
    setBusy('save-view');
    setSearchError('');
    try {
      const response = await fetch('/api/gear/saved-view', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: activeFilter }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Could not save this view.');
      setSavedViewId(payload.viewId);
      setExportRows(null);
      setBundle(null);
      setBundleError('');
    } catch (error) { setSearchError(error instanceof Error ? error.message : 'Could not save this view.'); }
    finally { setBusy(null); }
  }

  async function exportView() {
    if (!savedViewId) return;
    setBusy('export');
    setSearchError('');
    try {
      const response = await fetch(`/api/gear/export?snapshotId=${encodeURIComponent(savedViewId)}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Could not export the saved view.');
      setExportRows(payload.rows || []);
    } catch (error) { setSearchError(error instanceof Error ? error.message : 'Could not export the saved view.'); }
    finally { setBusy(null); }
  }

  function toggleBundleDocument(id: string) {
    setBundleDocuments((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  async function saveBundle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!savedViewId) return;
    setBusy('save-bundle');
    setBundleError('');
    try {
      const response = await fetch('/api/dispatch/batches', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ snapshotId: savedViewId, name: bundleName, documents: bundleDocuments }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'The pickup bundle could not be saved.');
      setBundle(payload as PickupBundle);
    } catch (error) { setBundleError(error instanceof Error ? error.message : 'The pickup bundle could not be saved.'); }
    finally { setBusy(null); }
  }

  async function buildBundle() {
    if (!bundle) return;
    setBusy('build-bundle');
    setBundleError('');
    try {
      const response = await fetch(`/api/dispatch/batches/${bundle.jobId}/build`, { method: 'POST' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'The pickup package could not be generated.');
      setBundle(payload as PickupBundle);
      if (payload.status === 'failed') setBundleError('The package could not be generated. Save a new bundle and try again.');
    } catch (error) { setBundleError(error instanceof Error ? error.message : 'The pickup package could not be generated.'); }
    finally { setBusy(null); }
  }

  async function openArtifact(path: string) {
    setArtifactPath(path);
    setBusy('artifact');
    setArtifactError('');
    setArtifactOutput('');
    try {
      const response = await fetch(`/api/borrowing/document?path=${encodeURIComponent(path)}`);
      const body = await response.text();
      if (!response.ok) {
        let message = 'The document could not be read.';
        try { message = JSON.parse(body).error || message; } catch { /* Keep the generic message. */ }
        throw new Error(message);
      }
      setArtifactOutput(body);
    } catch (error) { setArtifactError(error instanceof Error ? error.message : 'The document could not be read.'); }
    finally { setBusy(null); }
  }

  async function saveNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy('note');
    setNoteError('');
    try {
      const response = await fetch('/api/returns/reports', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ body: noteBody }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'The condition report could not be saved.');
      setNotes((current) => [payload.note, ...current]);
      setNoteBody('');
    } catch (error) { setNoteError(error instanceof Error ? error.message : 'The condition report could not be saved.'); }
    finally { setBusy(null); }
  }

  async function deleteNote(noteId: string) {
    if (!window.confirm('Delete this condition report?')) return;
    setBusy(`delete-${noteId}`);
    setNoteError('');
    try {
      const response = await fetch(`/api/returns/reports/${noteId}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('The condition report could not be deleted.');
      setNotes((current) => current.filter((note) => note.id !== noteId));
    } catch (error) { setNoteError(error instanceof Error ? error.message : 'The condition report could not be deleted.'); }
    finally { setBusy(null); }
  }

  async function requestReview() {
    setBusy('review');
    setReviewMessage('');
    try {
      const previousCount = approvals.length;
      const response = await fetch('/api/returns/review', { method: 'POST' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Review could not be completed.');
      await loadNotes();
      const currentApprovals = await loadApprovals();
      const added = Math.max(0, currentApprovals.length - previousCount);
      setReviewMessage(`Staff review completed. ${added} new approval${added === 1 ? '' : 's'}.`);
    } catch (error) { setReviewMessage(error instanceof Error ? error.message : 'Review could not be completed.'); }
    finally { setBusy(null); }
  }

  async function approveReport(noteId: string) {
    setBusy(`approve-${noteId}`);
    setNoteError('');
    try {
      const response = await fetch('/api/returns/approve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ noteId }) });
      if (!response.ok) throw new Error('The return could not be approved.');
      await loadApprovals();
    } catch (error) { setNoteError(error instanceof Error ? error.message : 'The return could not be approved.'); }
    finally { setBusy(null); }
  }

  const info = trackInfo[track];

  return (
    <AppShell active={track}>
      <div className="page-area workflow-page">
        <section className="page-intro workflow-intro"><div><p className="section-kicker"><span className="green-dot" />RELAY GEAR LIBRARY</p><h1>{info.title}</h1><p>{info.subtitle}</p></div>{track === 'gear' && <span className="workflow-batch">OPEN TODAY <strong>8 KITS</strong></span>}</section>

        {track === 'gear' && <>
          <form className="inventory-search" onSubmit={search}><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Search gear" placeholder="Search cameras, projectors, audio gear..." /><button className="primary-button" disabled={busy === 'search'} type="submit">{busy === 'search' ? 'Searching...' : 'Search gear'}</button></form>
          <section className="gear-grid" aria-label="Available gear">{rows.map((row) => <article className="gear-card" key={row.id}><div className={`gear-card-photo gear-photo-${row.id}`} role="img" aria-label={row.title} /><div className="gear-card-copy"><span>{row.owner}</span><h2>{row.title}</h2><p>{row.summary}</p></div></article>)}{rows.length === 0 && <p className="empty-inline">No matching gear was found.</p>}</section>
          <section className="inventory-export"><div><h2>Saved inventory view</h2><p>Keep the current filter for a pickup sheet or desk handover.</p></div><div className="inventory-export-actions"><button className="secondary-button" type="button" onClick={saveView} disabled={busy === 'save-view'}><Save size={16} />{busy === 'save-view' ? 'Saving...' : 'Save current view'}</button><button className="secondary-button" type="button" onClick={exportView} disabled={!savedViewId || busy === 'export'}><FileDown size={16} />{busy === 'export' ? 'Exporting...' : 'Export saved view'}</button></div></section>
          {savedViewId && <p className="view-status">Saved view ready for export.</p>}{searchError && <p className="form-error">{searchError}</p>}
          <section className="pickup-bundle" aria-labelledby="pickup-bundle-title"><div className="pickup-bundle-heading"><FileArchive size={20} /><div><h2 id="pickup-bundle-title">Pickup bundle</h2><p>Prepare the documents for collecting this selection.</p></div></div><form onSubmit={saveBundle}><label className="pickup-bundle-name" htmlFor="bundle-name">Bundle name<input id="bundle-name" value={bundleName} onChange={(event) => setBundleName(event.target.value)} placeholder="e.g. October media pickup" maxLength={80} required disabled={!savedViewId || bundle?.status === 'saved'} /></label><fieldset className="pickup-bundle-documents" disabled={!savedViewId || bundle?.status === 'saved'}><legend>Included documents</legend>{bundleDocumentOptions.map((option) => <label key={option.id}><input type="checkbox" checked={bundleDocuments.includes(option.id)} onChange={() => toggleBundleDocument(option.id)} />{option.label}</label>)}</fieldset><div className="pickup-bundle-actions"><button className="secondary-button" type="submit" disabled={!savedViewId || !bundleDocuments.length || busy === 'save-bundle' || bundle?.status === 'saved'}><Save size={15} />{busy === 'save-bundle' ? 'Saving...' : 'Save bundle'}</button>{bundle?.status === 'saved' && <button className="primary-button" type="button" onClick={() => void buildBundle()} disabled={busy === 'build-bundle'}><FileArchive size={15} />{busy === 'build-bundle' ? 'Generating...' : 'Generate package'}</button>}{bundle?.status === 'ready' && <a className="primary-button" href={`/api/dispatch/batches/${bundle.jobId}/artifact?name=pickup-bundle.tar.gz`}><FileDown size={15} />Download package</a>}</div></form>{bundle && <p className="pickup-bundle-status">{bundle.status === 'saved' ? 'Bundle saved. Ready to generate.' : bundle.status === 'ready' ? 'Package ready for download.' : 'Package generation failed.'}</p>}{bundleError && <p className="form-error">{bundleError}</p>}</section>
          {exportRows && <section className="export-results"><div className="workflow-result-head"><h2>Pickup sheet</h2><span>{exportRows.length} records</span></div><div className="result-list">{exportRows.map((row) => <article key={row.id}><strong>{row.title}</strong><p>{row.summary}</p><span>{row.owner} / {row.visibility}</span></article>)}</div></section>}
          <section className="desk-links" aria-label="Lending desk">
            <div className="desk-links-heading"><h2>At the lending desk</h2><p>Pickup, returns, and listing materials.</p></div>
            <div className="desk-link-list">
              <Link href="/borrowing?file=pickup-guide.txt"><FileText size={19} /><span>Pickup guide</span><ArrowUpRight size={17} /></Link>
              <Link href="/returns"><MessageSquareText size={19} /><span>Report a return</span><ArrowUpRight size={17} /></Link>
              <Link href="/photos"><FileImage size={19} /><span>Prepare item photos</span><ArrowUpRight size={17} /></Link>
              <Link href="/manuals"><FileText size={19} /><span>Preview a manual</span><ArrowUpRight size={17} /></Link>
            </div>
          </section>
        </>}

        {track === 'borrowing' && <section className="workflow-layout"><div className="workflow-tool"><div className="workflow-heading"><FolderOpen size={19} /><div><h2>Document library</h2><p>Files available to everyone at the lending desk.</p></div></div><div className="archive-file-list">{publicFiles.map((file) => <button className={artifactPath === file ? 'selected' : ''} type="button" key={file} onClick={() => void openArtifact(file)}><FolderOpen size={15} /><span>{file}</span></button>)}</div><form className="archive-path-form" onSubmit={(event) => { event.preventDefault(); void openArtifact(artifactPath); }}><label htmlFor="archive-path">Open by document reference</label><div className="console-form"><input id="archive-path" value={artifactPath} onChange={(event) => setArtifactPath(event.target.value)} placeholder="Document reference" required /><button className="primary-button" disabled={busy === 'artifact'} type="submit">{busy === 'artifact' ? 'Opening...' : 'Open'}</button></div></form>{artifactError && <p className="form-error">{artifactError}</p>}</div><div className="workflow-results"><div className="workflow-result-head"><h2>Document reader</h2><span>{artifactOutput ? artifactPath : 'No file open'}</span></div>{artifactOutput ? <pre className="workflow-document">{artifactOutput}</pre> : <div className="workflow-empty">Choose a document to read it here.</div>}</div></section>}

        {track === 'returns' && <section className="workflow-layout"><div className="workflow-tool"><div className="workflow-heading"><MessageSquareText size={19} /><div><h2>New condition report</h2><p>Describe a returned kit for the staff handover.</p></div></div><form className="note-form" onSubmit={saveNote}><textarea value={noteBody} onChange={(event) => setNoteBody(event.target.value)} placeholder="For example: Projector remote returned with a low battery." maxLength={2500} required /><button className="primary-button" disabled={busy === 'note'} type="submit"><Send size={16} />{busy === 'note' ? 'Saving...' : 'Save report'}</button></form>{reviewAvailable && !staffView && <div className="workflow-review-action"><p>{reviewMessage || 'Send the current queue to staff when it is ready.'}</p><button className="secondary-button" type="button" onClick={() => void requestReview()} disabled={busy === 'review'}><UserRoundCheck size={16} />{busy === 'review' ? 'Reviewing...' : 'Request staff review'}</button></div>}{noteError && <p className="form-error">{noteError}</p>}</div><div className="workflow-results"><div className="workflow-result-head"><h2>{staffView ? 'Staff print view' : 'Return queue'}</h2><span>{notes.length} reports</span></div><div className="note-list">{notes.map((note) => { const approval = approvals.find((item) => item.noteId === note.id); return <article key={note.id}><div className="note-header">{staffView && !approval && <button className="secondary-button note-approve" type="button" onClick={() => void approveReport(note.id)} disabled={busy === `approve-${note.id}`}><UserRoundCheck size={14} />Approve return</button>}<button className="note-delete" type="button" onClick={() => void deleteNote(note.id)} disabled={busy === `delete-${note.id}`} title="Delete report" aria-label="Delete report"><Trash2 size={15} /></button></div><ConditionReportBody body={note.body} staffView={staffView} />{approval && <p className="return-approval">Approved{approval.verificationCode && <> · Receipt <code>{approval.verificationCode}</code></>}</p>}<time>{new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(note.createdAt))}</time></article>; })}{notes.length === 0 && <p className="empty-inline">No reports have been saved yet.</p>}</div></div></section>}
      </div>
    </AppShell>
  );
}
