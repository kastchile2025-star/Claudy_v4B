import fs from 'fs';
import path from 'path';
import os from 'os';

export interface Skill {
  name: string;
  description: string;
  path: string;
  content: string;
}

export interface RemoteSkill {
  id: string;
  skillId: string;
  name: string;
  source: string;
  installs?: number;
  url?: string;
}

export interface SkillIntent {
  action: 'search' | 'install';
  query: string;
}

interface GithubRawInfo {
  owner: string;
  repo: string;
  branch: string;
  filePath: string;
  dirPath: string;
}

interface GithubContentItem {
  type: 'file' | 'dir';
  name: string;
  path: string;
  download_url?: string;
  size?: number;
}

const SKILLS_DIR = path.join(os.homedir(), '.claudy', 'skills');
const SKILLS_README = path.join(SKILLS_DIR, 'README.md');
const SKILLS_SEARCH_ENDPOINT = 'https://skills.sh/api/search';
const MAX_SKILL_ASSET_BYTES = 1_500_000;

export function getSkillsDir(): string {
  if (!fs.existsSync(SKILLS_DIR)) {
    fs.mkdirSync(SKILLS_DIR, { recursive: true });
  }
  return SKILLS_DIR;
}

function sanitizeSkillName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

function parseFrontmatter(content: string): { meta: Record<string, string>; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { meta: {}, body: content };

  const meta: Record<string, string> = {};
  for (const line of match[1].split('\n')) {
    const idx = line.indexOf(':');
    if (idx > 0) {
      const key = line.slice(0, idx).trim();
      const value = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
      meta[key] = value;
    }
  }
  return { meta, body: match[2] };
}

export function listSkills(): Skill[] {
  const dir = getSkillsDir();
  const skills: Skill[] = [];

  for (const entry of fs.readdirSync(dir)) {
    const skillDir = path.join(dir, entry);
    if (!fs.statSync(skillDir).isDirectory()) continue;

    const skillFile = path.join(skillDir, 'SKILL.md');
    if (!fs.existsSync(skillFile)) continue;

    try {
      const content = fs.readFileSync(skillFile, 'utf-8');
      const { meta, body } = parseFrontmatter(content);
      skills.push({
        name: meta.name || entry,
        description: meta.description || body.split('\n')[0].slice(0, 100),
        path: skillFile,
        content: body,
      });
    } catch {
      // skip
    }
  }

  return skills;
}

export function getSkill(name: string): Skill | null {
  return listSkills().find((s) => s.name === name) || null;
}

function escapeTable(value: string | undefined): string {
  return (value || '').replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
}

function readSourceMetadata(skillFile: string): Record<string, string> {
  const sourcePath = path.join(path.dirname(skillFile), 'source.json');
  if (!fs.existsSync(sourcePath)) return {};

  try {
    return JSON.parse(fs.readFileSync(sourcePath, 'utf-8')) as Record<string, string>;
  } catch {
    return {};
  }
}

export function updateSkillsReadme(): string {
  const skills = listSkills();
  const rows = skills.map((skill) => {
    const source = readSourceMetadata(skill.path);
    const sourceLabel = source.url || source.skillsUrl || source.id || 'local';
    return `| ${escapeTable(skill.name)} | ${escapeTable(skill.description)} | ${escapeTable(sourceLabel)} | ${escapeTable(skill.path)} |`;
  });

  const content = [
    '# Skills instalados en Claudy',
    '',
    'Este archivo se actualiza automaticamente cuando Claudy instala skills desde internet o desde una URL.',
    '',
    `Actualizado: ${new Date().toISOString()}`,
    '',
    '| Skill | Descripcion | Fuente | Ruta local |',
    '| --- | --- | --- | --- |',
    rows.length ? rows.join('\n') : '| _Sin skills instalados_ |  |  |  |',
    '',
    'Nota: los skills son instrucciones Markdown. Instala solo fuentes confiables.',
    '',
  ].join('\n');

  fs.writeFileSync(SKILLS_README, content, 'utf-8');
  return SKILLS_README;
}

function cleanSkillQuery(message: string): string {
  const normalized = message
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[¿?!.:,;]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const afterPara = normalized.match(/\b(?:para|sobre|de)\s+(.+)$/)?.[1] || normalized;

  return afterPara
    .replace(
      /\b(instala|instalar|instales|instale|instalarme|instalarla|agrega|agregar|anade|anadir|busca|buscar|busques|busque|encuentra|encontrar|skill|skills|habilidad|habilidades|una|un|el|la|los|las|que|yo|quiero|necesito|pueda|puedas|poder|utilizar|utilizarla|usar|hacer|leer|lectura|abrir|procesar|analizar)\b/g,
      ' '
    )
    .replace(/\s+/g, ' ')
    .trim();
}

export function parseSkillIntent(message: string): SkillIntent | null {
  const normalized = message.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const mentionsSkill = /\b(skill|skills|habilidad|habilidades)\b/.test(normalized);
  if (!mentionsSkill) return null;

  const looksLikeQuestion =
    /[¿?]/.test(message) && /\b(puedo|podemos|como|que|cual|cuanto)\b/.test(normalized);
  if (looksLikeQuestion) return null;

  const wantsInstall = /\b(instala|instalar|instales|instale|instalarme|instalarla|agrega|agregar|anade|anadir|install|add)\b/.test(
    normalized
  );
  const wantsSearch = /\b(busca|buscar|busques|busque|encuentra|encontrar|find|search)\b/.test(
    normalized
  );
  if (!wantsInstall && !wantsSearch) return null;

  const query = cleanSkillQuery(message);
  if (!query || query.length < 2) return null;
  return { action: wantsInstall ? 'install' : 'search', query };
}

function githubBlobToRaw(url: string): string {
  return url
    .replace('github.com', 'raw.githubusercontent.com')
    .replace('/blob/', '/');
}

export async function installSkillFromUrl(
  url: string,
  customName?: string
): Promise<{ name: string; path: string }> {
  const rawUrl = githubBlobToRaw(url);
  const res = await fetch(rawUrl);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  const content = await res.text();

  // Intentar nombre desde frontmatter, luego desde URL
  const { meta } = parseFrontmatter(content);
  let name = customName || meta.name;
  if (!name) {
    // Extraer del path: skills/find-skills/SKILL.md → find-skills
    const parts = rawUrl.split('/').filter(Boolean);
    const skillIdx = parts.findIndex((p) => p.toLowerCase() === 'skills');
    if (skillIdx >= 0 && parts[skillIdx + 1]) {
      name = parts[skillIdx + 1];
    } else {
      name = 'skill-' + Date.now().toString(36);
    }
  }

  name = sanitizeSkillName(name);
  const filePath = saveSkillFromContent(name, content);
  const assetFiles = await downloadGithubSkillAssets(rawUrl, path.dirname(filePath));
  fs.writeFileSync(
    path.join(path.dirname(filePath), 'source.json'),
    JSON.stringify(
      { url: rawUrl, files: ['SKILL.md', ...assetFiles], installedAt: new Date().toISOString() },
      null,
      2
    ),
    'utf-8'
  );
  updateSkillsReadme();
  return { name, path: filePath };
}

export function findSkillUrls(text: string): string[] {
  // Match URLs que apunten a SKILL.md (raw o blob)
  const re =
    /https?:\/\/(?:raw\.githubusercontent\.com|github\.com)\/[\w.-]+\/[\w.-]+\/(?:blob\/)?[\w.-/]+SKILL\.md/gi;
  const matches = text.match(re) || [];
  return [...new Set(matches)];
}

export function saveSkillFromContent(name: string, content: string): string {
  const dir = getSkillsDir();
  const skillDir = path.join(dir, sanitizeSkillName(name));
  fs.mkdirSync(skillDir, { recursive: true });
  const filePath = path.join(skillDir, 'SKILL.md');
  fs.writeFileSync(filePath, content, 'utf-8');
  return filePath;
}

function remoteSkillRawUrlCandidates(skill: RemoteSkill): string[] {
  if (!skill.source.includes('/')) return [];

  const skillId = sanitizeSkillName(skill.skillId || skill.name);
  const branches = ['main', 'master'];
  const paths = [
    `skills/${skillId}/SKILL.md`,
    `${skillId}/SKILL.md`,
    `.claude/skills/${skillId}/SKILL.md`,
    `.github/copilot/skills/${skillId}/SKILL.md`,
    `.github/skills/${skillId}/SKILL.md`,
  ];

  return branches.flatMap((branch) =>
    paths.map((p) => `https://raw.githubusercontent.com/${skill.source}/${branch}/${p}`)
  );
}

async function fetchRemoteSkillContent(skill: RemoteSkill): Promise<{
  content: string;
  sourceUrl: string;
}> {
  for (const url of remoteSkillRawUrlCandidates(skill)) {
    try {
      const res = await fetch(url, { headers: { 'User-Agent': 'Claudy/0.1' } });
      if (!res.ok) continue;
      const content = await res.text();
      if (!content.trim()) continue;
      return { content, sourceUrl: url };
    } catch {
      // probar siguiente ruta candidata
    }
  }

  throw new Error(`No pude encontrar SKILL.md para ${skill.id}.`);
}

function parseGithubRawUrl(rawUrl: string): GithubRawInfo | null {
  const url = new URL(rawUrl);
  if (url.hostname !== 'raw.githubusercontent.com') return null;

  const [owner, repo, branch, ...pathParts] = url.pathname.split('/').filter(Boolean);
  if (!owner || !repo || !branch || pathParts.length === 0) return null;
  if (pathParts[pathParts.length - 1].toLowerCase() !== 'skill.md') return null;

  return {
    owner,
    repo,
    branch,
    filePath: pathParts.join('/'),
    dirPath: pathParts.slice(0, -1).join('/'),
  };
}

function encodeGithubPath(githubPath: string): string {
  return githubPath.split('/').map(encodeURIComponent).join('/');
}

function safeGithubRelativePath(baseDir: string, itemPath: string): string | null {
  const relative = path.posix.relative(baseDir, itemPath);
  if (!relative || relative.startsWith('..') || path.posix.isAbsolute(relative)) return null;

  const parts = relative.split('/');
  if (parts.some((part) => !part || part === '.' || part === '..')) return null;
  return parts.join('/');
}

async function listGithubDirectory(
  info: GithubRawInfo,
  dirPath: string,
  depth = 0
): Promise<GithubContentItem[]> {
  if (depth > 4) return [];

  const url = new URL(
    `https://api.github.com/repos/${info.owner}/${info.repo}/contents/${encodeGithubPath(dirPath)}`
  );
  url.searchParams.set('ref', info.branch);

  const response = await fetch(url, {
    headers: {
      Accept: 'application/vnd.github+json',
      'User-Agent': 'Claudy/0.1',
    },
  });
  if (!response.ok) return [];

  const payload = (await response.json()) as GithubContentItem[] | GithubContentItem;
  const items = Array.isArray(payload) ? payload : [payload];
  const files: GithubContentItem[] = [];

  for (const item of items) {
    if (item.type === 'file') {
      files.push(item);
    } else if (item.type === 'dir') {
      files.push(...(await listGithubDirectory(info, item.path, depth + 1)));
    }
  }

  return files;
}

async function downloadGithubSkillAssets(sourceUrl: string, destinationDir: string): Promise<string[]> {
  const info = parseGithubRawUrl(sourceUrl);
  if (!info) return [];

  const files = await listGithubDirectory(info, info.dirPath);
  const written: string[] = [];
  let totalBytes = 0;

  for (const file of files) {
    const relativePath = safeGithubRelativePath(info.dirPath, file.path);
    if (!relativePath || relativePath.toLowerCase() === 'skill.md') continue;

    const downloadUrl =
      file.download_url ||
      `https://raw.githubusercontent.com/${info.owner}/${info.repo}/${info.branch}/${file.path}`;
    const response = await fetch(downloadUrl, { headers: { 'User-Agent': 'Claudy/0.1' } });
    if (!response.ok) continue;

    const bytes = Buffer.from(await response.arrayBuffer());
    totalBytes += bytes.length;
    if (totalBytes > MAX_SKILL_ASSET_BYTES) {
      throw new Error('Los archivos auxiliares del skill exceden el limite permitido.');
    }

    const target = path.join(destinationDir, ...relativePath.split('/'));
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, bytes);
    written.push(relativePath);
  }

  return written;
}

export async function removeSkill(name: string): Promise<boolean> {
  const dir = getSkillsDir();
  const skillDir = path.join(dir, name);
  if (!fs.existsSync(skillDir)) return false;
  fs.rmSync(skillDir, { recursive: true, force: true });
  return true;
}


// ─── TF-IDF local para ranking de skills ─────────────────────────────────
const STOP_WORDS = new Set([
  'de','la','el','en','y','a','los','del','las','un','por','con','una','su',
  'para','es','al','lo','como','si','se','su','yo','no','sin','son',
  'the','a','an','is','in','of','to','it','and','or','be','as','at','by',
  'we','for','on','with','not','but','have','from','what','you','can',
]);

function tokenizeLocal(text: string): string[] {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 2 && !STOP_WORDS.has(t));
}

function tfidfScore(queryTokens: string[], skill: Skill): number {
  const nameTokens = tokenizeLocal(skill.name);
  const descTokens = tokenizeLocal(skill.description);
  const bodyTokens = tokenizeLocal(skill.content.slice(0, 5_000));

  let score = 0;
  for (const qt of queryTokens) {
    // Pesos: nombre ×10, descripción ×5, cuerpo ×1
    if (nameTokens.includes(qt)) score += 10;
    if (descTokens.includes(qt)) score += 5;
    if (bodyTokens.includes(qt)) score += 1;
  }
  return score;
}

export function findRelevantSkills(query: string, max = 3): Skill[] {
  const skills = listSkills();
  const queryTokens = tokenizeLocal(query);
  if (queryTokens.length === 0) return [];

  return skills
    .map((skill) => ({ skill, score: tfidfScore(queryTokens, skill) }))
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, max)
    .map((s) => s.skill);
}

export function buildSkillsContext(skills: Skill[]): string {
  if (skills.length === 0) return '';
  return (
    '\n\n=== SKILLS RELEVANTES ===\n' +
    skills
      .map((s) => `[Skill: ${s.name}]\n${s.content.slice(0, 4000)}`)
      .join('\n\n---\n\n') +
    '\n=== FIN SKILLS ==='
  );
}

// ─── Delegación al backend (si está corriendo) ────────────────────────────
/**
 * Intenta usar el backend Claudy (puerto configurable) como proxy
 * para las operaciones remotas. Si no está disponible, cae al código local.
 */
async function tryBackendProxy<T>(
  url: string,
  options?: RequestInit
): Promise<T | null> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(3_000), ...options });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

function backendBase(): string {
  // Permite configurar el puerto del backend via variable de entorno
  return process.env.CLAUDY_BACKEND_URL || 'http://127.0.0.1:3001';
}

/**
 * Busca skills remotos: primero intenta el backend Claudy,
 * luego cae directamente a skills.sh.
 */
export async function searchRemoteSkills(query: string, limit = 8): Promise<RemoteSkill[]> {
  // Intentar delegar al backend
  const backendUrl = `${backendBase()}/api/skills/remote-search?q=${encodeURIComponent(query)}`;
  const backendResult = await tryBackendProxy<RemoteSkill[]>(backendUrl);
  if (backendResult && Array.isArray(backendResult)) {
    return backendResult.slice(0, limit);
  }

  // Fallback directo a skills.sh
  const url = new URL(SKILLS_SEARCH_ENDPOINT);
  url.searchParams.set('q', query);

  const res = await fetch(url, { headers: { 'User-Agent': 'Claudy/0.1' } });
  if (!res.ok) throw new Error(`No pude buscar en skills.sh (${res.status}).`);

  const data = (await res.json()) as { skills?: RemoteSkill[]; data?: RemoteSkill[] };
  const skills = data.skills || data.data || [];
  const seen = new Set<string>();

  return skills
    .filter((skill) => skill.id && skill.skillId && skill.source && !seen.has(skill.id))
    .filter((skill) => { seen.add(skill.id); return true; })
    .sort((a, b) => (b.installs || 0) - (a.installs || 0))
    .slice(0, limit);
}

export async function installRemoteSkill(skill: RemoteSkill): Promise<{
  name: string;
  path: string;
  sourceUrl: string;
  readmePath: string;
}> {
  const { content, sourceUrl } = await fetchRemoteSkillContent(skill);
  const { meta } = parseFrontmatter(content);
  const name = sanitizeSkillName(meta.name || skill.skillId || skill.name);
  const filePath = saveSkillFromContent(name, content);
  const assetFiles = await downloadGithubSkillAssets(sourceUrl, path.dirname(filePath));

  fs.writeFileSync(
    path.join(path.dirname(filePath), 'source.json'),
    JSON.stringify(
      {
        id: skill.id,
        source: skill.source,
        skillId: skill.skillId,
        installs: skill.installs || 0,
        skillsUrl: skill.url || `https://skills.sh/${skill.id}`,
        url: sourceUrl,
        files: ['SKILL.md', ...assetFiles],
        installedAt: new Date().toISOString(),
      },
      null,
      2
    ),
    'utf-8'
  );

  return {
    name,
    path: filePath,
    sourceUrl,
    readmePath: updateSkillsReadme(),
  };
}

export async function installBestSkillForQuery(query: string): Promise<{
  installed: { name: string; path: string; sourceUrl: string; readmePath: string };
  remote: RemoteSkill;
  candidates: RemoteSkill[];
}> {
  // Intentar delegar instalación al backend
  const backendUrl = `${backendBase()}/api/skills/install-best`;
  const backendResult = await tryBackendProxy<{
    skill: { name: string; path: string };
    sourceUrl: string;
    readmePath: string;
  }>(backendUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });

  if (backendResult && backendResult.skill?.name) {
    // El backend instaló — también refrescar el readme local
    const candidates = await searchRemoteSkills(query, 8).catch(() => []);
    const remote = candidates[0] || { id: query, skillId: query, name: query, source: 'unknown' };
    return {
      installed: {
        name: backendResult.skill.name,
        path: backendResult.skill.path,
        sourceUrl: backendResult.sourceUrl || '',
        readmePath: backendResult.readmePath || '',
      },
      remote,
      candidates,
    };
  }

  // Fallback: instalación local
  const candidates = await searchRemoteSkills(query, 8);
  if (candidates.length === 0) throw new Error(`No encontre skills para "${query}".`);

  const errors: string[] = [];
  for (const candidate of candidates) {
    try {
      const installed = await installRemoteSkill(candidate);
      return { installed, remote: candidate, candidates };
    } catch (err: any) {
      errors.push(`${candidate.id}: ${err.message || String(err)}`);
    }
  }

  throw new Error(`Encontre candidatos, pero no pude instalar ninguno:\n${errors.join('\n')}`);
}
