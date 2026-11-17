'use client';

import { ExternalLink, ImageIcon, LoaderCircle, RefreshCw, SlidersHorizontal, Upload } from 'lucide-react';
import { ChangeEvent, useState } from 'react';
import { AppShell } from '@/components/app-shell';

type TransformResult = {
  jobId: string;
  operation: string;
  inputName: string;
  createdAt: string;
  summary: string;
  ok?: boolean;
  workerOutput?: string;
  artifacts?: string[];
  observer?: { artifacts: { name: string; location: string; content: string }[] };
};

type TraceEntry = {
  method: string;
  path: string;
  query: string;
  observedAt: string;
};

type ObserverArtifact = { name: string; location: string; content: string };

const operationLabels: Record<string, string> = {
  thumbnail: 'Thumbnail preview',
  grayscale: 'Grayscale preview',
  metadata: 'Clean preview',
};

const inputBasenames: Record<string, string> = {
  thumbnail: 'img_trans1_thumpreview',
  grayscale: 'img_trans2_grayscale',
  metadata: 'img_trans3_metadata',
};

function normalizedInputName(filename: string, operation: string) {
  const basename = filename.replace(/^.*[\\/]/, '');
  const extensionStart = basename.lastIndexOf('.');
  const extension = extensionStart > 0 ? basename.slice(extensionStart) : '.bin';
  return `${inputBasenames[operation] || 'img_transform'}${extension}`;
}

export function ItemPhotos() {
  const [file, setFile] = useState<File | null>(null);
  const [reference, setReference] = useState<File | null>(null);
  const [operation, setOperation] = useState('thumbnail');
  const [result, setResult] = useState<TransformResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState<TraceEntry[]>([]);
  const [traceBusy, setTraceBusy] = useState(false);
  const [observer, setObserver] = useState<ObserverArtifact[]>([]);
  const [observerBusy, setObserverBusy] = useState(false);
  const [observerJobId, setObserverJobId] = useState('');

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] || null);
    setResult(null);
    setError('');
    setTrace([]);
    setObserver([]);
    setObserverJobId('');
  }

  async function refreshTrace() {
    setTraceBusy(true);
    try {
      const response = await fetch('/api/photos/trace', { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      setTrace(Array.isArray(payload.requests) ? payload.requests as TraceEntry[] : []);
    } catch {
      setTrace([]);
    } finally {
      setTraceBusy(false);
    }
  }

  async function refreshObserver(jobId: string) {
    setObserverBusy(true);
    try {
      const response = await fetch(`/api/photos/jobs/${jobId}/observer`, { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      setObserver(Array.isArray(payload.artifacts) ? payload.artifacts as ObserverArtifact[] : []);
    } catch {
      setObserver([]);
    } finally {
      setObserverBusy(false);
    }
  }

  async function submitTransform(sample: boolean) {
    if (!sample && !file) {
      setError('Choose an image file or load the sample image.');
      return;
    }
    setBusy(true);
    setError('');
    setResult(null);
    setTrace([]);
    setObserver([]);
    setObserverJobId('');
    const body = new FormData();
    body.set('operation', operation);
    body.set('sample', String(sample));
    if (file && !sample) body.set('file', file);
    if (reference && !sample) body.set('reference', reference);
    try {
      const response = await fetch('/api/photos/transform', { method: 'POST', body });
      const payload = await response.json().catch(() => ({}));
      if (payload.jobId) {
        setObserverJobId(payload.jobId as string);
        void refreshTrace();
        void refreshObserver(payload.jobId as string);
      }
      if (!response.ok) {
        const artifacts = Array.isArray(payload.artifacts) ? payload.artifacts as string[] : [];
        setResult({
          jobId: payload.jobId as string,
          operation: payload.operation || operation,
          inputName: payload.inputName || (sample ? `${inputBasenames[operation]}.png` : file ? normalizedInputName(file.name, operation) : `${inputBasenames[operation]}.bin`),
          createdAt: payload.createdAt || '',
          summary: payload.error || 'The image operation could not be completed.',
          ok: false,
          workerOutput: payload.workerOutput as string | undefined,
          artifacts,
        });
        setError(payload.workerOutput ? `${payload.error} ${payload.workerOutput}` : payload.error || 'The image operation could not be completed.');
        return;
      }
      setResult({ ...(payload as TransformResult), ok: true });
      void refreshTrace();
    } catch {
      setError('The image worker is not available.');
    } finally {
      setBusy(false);
    }
  }

  const observerTarget = result?.jobId || observerJobId;

  return (
    <AppShell active="photos">
      <div className="page-area component-page">
        <section className="page-intro">
          <div>
            <p className="section-kicker"><span className="green-dot" />RELAY GEAR LIBRARY</p>
            <h1>Item photos</h1>
            <p>Make consistent thumbnails for gear listings and return records.</p>
          </div>
        </section>
        <section className="component-workbench">
          <form className="component-control-panel" onSubmit={(event) => { event.preventDefault(); void submitTransform(false); }}>
            <div className="panel-title-row"><div><ImageIcon size={18} /><div><strong>Source image</strong><span>Local transformation request</span></div></div></div>
            <label className="file-picker"><span><Upload size={17} />{file ? normalizedInputName(file.name, operation) : 'Choose image file'}</span><input type="file" accept=".bmp,.gif,.jpeg,.jpg,.mvg,.png,.ppm,.svg,.tif,.tiff,.webp" onChange={selectFile} /></label>
            <label className="file-picker related-file-picker"><span><Upload size={17} />{reference ? reference.name : 'Add related file (optional)'}</span><input type="file" onChange={(event) => setReference(event.target.files?.[0] || null)} /></label>
            <label className="component-field"><span>Operation</span><select value={operation} onChange={(event) => setOperation(event.target.value)}>{Object.entries(operationLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <div className="component-actions">
              <button className="secondary-button" type="button" disabled={busy} onClick={() => void submitTransform(true)}><RefreshCw size={16} />Load sample</button>
              <button className="primary-button" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <SlidersHorizontal size={16} />}{busy ? 'Processing...' : 'Create preview'}</button>
            </div>
            {error && <p className="form-error">{error}</p>}
            <dl className="component-facts"><div><dt>Execution</dt><dd>Isolated local worker</dd></div><div><dt>Input limit</dt><dd>6 MB per request</dd></div></dl>
          </form>

          <section className="component-result-panel">
            <div className="panel-title-row"><div><ImageIcon size={18} /><div><strong>Rendered preview</strong><span>Worker output</span></div></div></div>
            {result ? result.ok === false ? <div className="component-complete"><ImageIcon size={30} /><strong>Worker returned an error</strong><p>{result.summary}</p>{result.artifacts?.length ? <><span className="observer-output-label">Job artifacts</span><div className="artifact-links">{result.artifacts.map((name) => <a key={name} href={`/api/photos/jobs/${result.jobId}/artifact?name=${encodeURIComponent(name)}`} target="_blank" rel="noreferrer"><ExternalLink size={13} />{name}</a>)}</div></> : null}</div> : <div className="artifact-result"><img src={`/api/photos/jobs/${result.jobId}/result`} alt={`Preview generated from ${result.inputName}`} /><div className="artifact-summary"><strong>{result.inputName}</strong><span>{operationLabels[result.operation] || result.operation}</span><code>{result.summary}</code>{result.artifacts?.length ? <div className="artifact-links">{result.artifacts.map((name) => <a key={name} href={`/api/photos/jobs/${result.jobId}/artifact?name=${encodeURIComponent(name)}`} target="_blank" rel="noreferrer"><ExternalLink size={13} />{name}</a>)}</div> : null}</div></div> : <div className="component-empty"><ImageIcon size={28} /><p>Preview output will appear here.</p></div>}
          </section>
        </section>

        <section className="component-observer-panel">
          <div className="observer-heading"><div><RefreshCw size={17} /><div><strong>Internal request observer</strong><span>Requests recorded by the isolated lab service</span></div></div><button className="secondary-button" type="button" onClick={() => void refreshTrace()} disabled={traceBusy}>{traceBusy ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />}Refresh trace</button></div>
          {trace.length ? <div className="trace-list">{trace.map((entry, index) => <div className="trace-row" key={`${entry.observedAt}-${index}`}><code>{entry.method}</code><span>{entry.path}{entry.query ? `?${entry.query}` : ''}</span><time>{entry.observedAt}</time></div>)}</div> : <p className="observer-empty">No internal request has been recorded for this local run.</p>}
        </section>

        <section className="component-observer-panel">
          <div className="observer-heading"><div><ImageIcon size={17} /><div><strong>Sandbox evidence</strong><span>External files only; job-local files appear under Worker output</span></div></div>{observerTarget ? <button className="secondary-button" type="button" onClick={() => void refreshObserver(observerTarget)} disabled={observerBusy}>{observerBusy ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />}Refresh evidence</button> : null}</div>
          {observer.length ? <div className="observer-artifacts">{observer.map((item) => <article key={`${item.location}-${item.name}`}><div><strong>{item.name}</strong><span>{item.location}</span></div><pre className="observer-code">{item.content}</pre></article>)}</div> : <p className="observer-empty">No sandbox evidence has been recorded for this local run.</p>}
        </section>
      </div>
    </AppShell>
  );
}
