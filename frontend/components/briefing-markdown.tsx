import type {ReactNode} from 'react';

/** Small safe formatter for agent-authored prose, NOT a general HTML/Markdown renderer. */
export function normalizeBriefing(raw:string):string {
  const decoded=raw.includes('\\n')&&!raw.includes('\n')?raw.replaceAll('\\n','\n'):raw;
  return decoded
    .replace(/\$?\\(?:rightarrow|to)\$?/g,' → ')
    .replace(/\$\s*→\s*\$/g,' → ')
    .replace(/\\([*#_\-])/g,'$1')
    .replace(/(^|\n)\s*[•*]\s*-\s+/g,'$1- ')
    .replace(/(^|\n)\s*[-•]\s*[•*-]\s+/g,'$1- ')
    .replace(/(^|\n)\s*(\d+)\\\.\s+/g,'$1$2. ')
    .replace(/([^\n])\s+(#{2,6}\s)/g,'$1\n$2')
    .replace(/\s+(\d+)\.\s+(?=\*\*)/g,'\n$1. ');
}
function inline(text:string):ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).filter(Boolean).map((piece,i)=>{
    if(piece.startsWith('**')&&piece.endsWith('**'))return <strong key={i}>{piece.slice(2,-2)}</strong>;
    if(piece.startsWith('`')&&piece.endsWith('`'))return <code key={i}>{piece.slice(1,-1)}</code>;
    if(piece.startsWith('*')&&piece.endsWith('*'))return <em key={i}>{piece.slice(1,-1)}</em>;
    return piece;
  });
}
export default function BriefingMarkdown({text}:{text:string}) {
  const lines=normalizeBriefing(text).split('\n');
  const blocks:{kind:'paragraph'|'list'|'heading';lines:string[]}[]=[];
  for(const raw of lines){
    const line=raw.trim();
    if(!line)continue;
    const bullet=/^(?:[-•*]\s+|\d+[.)]\s+)/.test(line);
    const heading=/^#{1,6}\s+/.test(line)||/^\*\*[^*]+\*\*:?$/.test(line);
    const kind=bullet?'list':heading?'heading':'paragraph';
    if(kind==='list'&&blocks.at(-1)?.kind==='list')blocks.at(-1)!.lines.push(line.replace(/^(?:[-•*]\s+|\d+[.)]\s+)/,''));
    else if(kind==='paragraph'&&blocks.at(-1)?.kind==='paragraph')blocks.at(-1)!.lines.push(line);
    else blocks.push({kind,lines:[kind==='list'?line.replace(/^(?:[-•*]\s+|\d+[.)]\s+)/,''):line]});
  }
  return <div className="v7ReadableBriefing">{blocks.map((b,i)=>{
    if(b.kind==='list')return <ul key={i}>{b.lines.map((line,j)=><li key={j}>{inline(line)}</li>)}</ul>;
    if(b.kind==='heading')return <h4 key={i}>{inline(b.lines[0].replace(/^#{1,6}\s+/,''))}</h4>;
    return <p key={i}>{b.lines.map((line,j)=><span key={j}>{inline(line)}{j<b.lines.length-1&&' '}</span>)}</p>;
  })}</div>;
}
