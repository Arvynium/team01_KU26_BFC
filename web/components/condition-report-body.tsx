'use client';

import { useMemo } from 'react';

function escapeNoteText(value: string) {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  })[character] || character);
}

function formatConditionReport(value: string, staffView: boolean) {
  const source = staffView ? value : escapeNoteText(value);
  return source
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/\[\[([^\]\n]{1,80})\]\]/g, '<mark>$1</mark>')
    .replace(/\r?\n/g, '<br />');
}

export function ConditionReportBody({ body, staffView = false }: { body: string; staffView?: boolean }) {
  const formatted = useMemo(() => formatConditionReport(body, staffView), [body, staffView]);
  return <div className="note-body" dangerouslySetInnerHTML={{ __html: formatted }} />;
}
