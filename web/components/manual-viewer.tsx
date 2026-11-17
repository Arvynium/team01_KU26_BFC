'use client';

import { ExternalLink, FileImage, FileText, LoaderCircle, RefreshCw, Upload } from 'lucide-react';
import { ChangeEvent, useState } from 'react';
import { AppShell } from '@/components/app-shell';

type RenderResult = {
  jobId: string;
  profile: string;
  inputName: string;
  createdAt: string;
  summary: string;
  observedOutput?: string;
  artifacts?: string[];
  observer?: { artifacts: { name: string; location: string; content: string }[] };
};

type ObserverArtifact = { name: string; location: string; content: string };

const profileLabels: Record<string, string> = {
  screen: 'Screen preview',
  archive: 'Archive preview',
  export: 'Document export',
  'mode-a': 'Mode A',
  'mode-b': 'Mode B',
};

const inputBasenames: Record<string, string> = {
  screen: 'doc_preview1_screen',
  archive: 'doc_preview2_archive',
  export: 'doc_preview3_export',
  'mode-a': 'doc_preview4_mode_a',
  'mode-b': 'doc_preview5_mode_b',
};

function normalizedInputName(filename: string, profile: string) {
  const basename = filename.replace(/^.*[\\/]/, '');
  const extensionStart = basename.lastIndexOf('.');
  const extension = extensionStart > 0 ? basename.slice(extensionStart) : '.bin';
  return `${inputBasenames[profile] || 'doc_preview'}${extension}`;
}

function JobArtifactLinks({ result }: { result: RenderResult }) {
  const names = (result.artifacts || []).filter((name) => name !== 'preview.png');
  if (!names.length) return null;
  return <><span className="observer-output-label">Job artifacts</span><div className="artifact-links">{names.map((name) => <a key={name} href={`/api/manuals/jobs/${result.jobId}/artifact?name=${encodeURIComponent(name)}`} target="_blank" rel="noreferrer"><ExternalLink size={13} />{name}</a>)}</div></>;
}

export function ManualViewer() {
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState('screen');
  const [result, setResult] = useState<RenderResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [observer, setObserver] = useState<ObserverArtifact[]>([]);
  const [observerBusy, setObserverBusy] = useState(false);
  const [observerJobId, setObserverJobId] = useState('');

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] || null);
    setResult(null);
    setError('');
    setObserver([]);
    setObserverJobId('');
  }

  async function refreshObserver(jobId: string) {
    setObserverBusy(true);
    try {
      const response = await fetch(`/api/manuals/jobs/${jobId}/observer`, { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      setObserver(Array.isArray(payload.artifacts) ? payload.artifacts as ObserverArtifact[] : []);
    } catch {
      setObserver([]);
    } finally {
      setObserverBusy(false);
    }
  }

  async function submitDocument(sample: boolean) {
    if (!sample && !file) {
      setError('Choose a PDF or PostScript file or load the sample document.');
      return;
    }
    setBusy(true);
    setError('');
    setResult(null);
    setObserver([]);
    setObserverJobId('');
    const body = new FormData();
    body.set('profile', profile);
    body.set('sample', String(sample));
    if (file && !sample) body.set('file', file);
    try {
      const response = await fetch('/api/manuals/render', { method: 'POST', body });
      const payload = await response.json().catch(() => ({}));
      if (payload.jobId) {
        setObserverJobId(payload.jobId as string);
        void refreshObserver(payload.jobId as string);
      }
      if (!response.ok) {
        setError(payload.workerOutput ? `${payload.error} ${payload.workerOutput}` : payload.error || 'The document operation could not be completed.');
        return;
      }
      setResult(payload as RenderResult);
    } catch {
      setError('The document worker is not available.');
    } finally {
      setBusy(false);
    }
  }

  const observerTarget = result?.jobId || observerJobId;

  return (
    <AppShell active="manuals">
      <div className="page-area component-page">
        <section className="page-intro">
          <div>
            <p className="section-kicker"><span className="green-dot" />RELAY GEAR LIBRARY</p>
            <h1>Manual viewer</h1>
            <p>Preview equipment manuals and print-ready loan documents.</p>
          </div>
        </section>
        <section className="component-workbench">
          <form className="component-control-panel" onSubmit={(event) => { event.preventDefault(); void submitDocument(false); }}>
            <div className="panel-title-row"><div><FileText size={18} /><div><strong>Source document</strong><span>Local rendering request</span></div></div></div>
            <label className="file-picker"><span><Upload size={17} />{file ? normalizedInputName(file.name, profile) : 'Choose PDF or PostScript'}</span><input type="file" accept=".pdf,.ps,.eps" onChange={selectFile} /></label>
            <label className="component-field"><span>Profile</span><select value={profile} onChange={(event) => setProfile(event.target.value)}>{Object.entries(profileLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <div className="component-actions">
              <button className="secondary-button" type="button" disabled={busy} onClick={() => void submitDocument(true)}><RefreshCw size={16} />Load sample</button>
              <button className="primary-button" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <FileImage size={16} />}{busy ? 'Rendering...' : 'Render preview'}</button>
            </div>
            {error && <p className="form-error">{error}</p>}
            <dl className="component-facts"><div><dt>Execution</dt><dd>Isolated local worker</dd></div><div><dt>Input limit</dt><dd>8 MB per request</dd></div></dl>
          </form>

          <section className="component-result-panel">
            <div className="panel-title-row"><div><FileText size={18} /><div><strong>Rendered page</strong><span>Worker output</span></div></div></div>
            {result && (result.profile === 'screen' || result.profile === 'archive') ? <div className="artifact-result"><img src={`/api/manuals/jobs/${result.jobId}/result`} alt={`Preview generated from ${result.inputName}`} /><div className="artifact-summary"><strong>{result.inputName}</strong><span>{profileLabels[result.profile] || result.profile}</span><code>{result.summary}</code>{result.observedOutput ? <><span className="observer-output-label">Observed worker output</span><pre className="observer-code">{result.observedOutput}</pre></> : null}<JobArtifactLinks result={result} /></div></div> : result ? <div className="component-complete"><FileText size={30} /><strong>{profileLabels[result.profile]}</strong><p>{result.summary}</p>{result.observedOutput ? <><span className="observer-output-label">Observed worker output</span><pre className="observer-code">{result.observedOutput}</pre></> : null}<JobArtifactLinks result={result} /></div> : <div className="component-empty"><FileText size={28} /><p>Rendered page output will appear here.</p></div>}
          </section>
        </section>

        <section className="component-observer-panel">
          <div className="observer-heading"><div><FileText size={17} /><div><strong>Sandbox evidence</strong><span>Files observed outside the normal preview result</span></div></div>{observerTarget ? <button className="secondary-button" type="button" onClick={() => void refreshObserver(observerTarget)} disabled={observerBusy}>{observerBusy ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />}Refresh evidence</button> : null}</div>
          {observer.length ? <div className="observer-artifacts">{observer.map((item) => <article key={`${item.location}-${item.name}`}><div><strong>{item.name}</strong><span>{item.location}</span></div><pre className="observer-code">{item.content}</pre></article>)}</div> : <p className="observer-empty">No sandbox evidence has been recorded for this local run.</p>}
        </section>
      </div>
    </AppShell>
  );
}
