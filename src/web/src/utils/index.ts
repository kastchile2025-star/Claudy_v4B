import { formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'

/**
 * Formatea una fecha relativa en español
 */
export const formatDate = (date: Date): string => {
  return formatDistanceToNow(new Date(date), {
    addSuffix: true,
    locale: es,
  })
}

/**
 * Genera un ID único
 */
export const generateId = (prefix: string = ''): string => {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

/**
 * Trunca texto a cierta longitud
 */
export const truncateText = (text: string, length: number = 50): string => {
  if (text.length <= length) return text
  return text.substring(0, length) + '...'
}

/**
 * Copia texto al portapapeles
 */
export const copyToClipboard = async (text: string): Promise<void> => {
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error('Error copying to clipboard:', err)
    throw err
  }
}

/**
 * Parsea respuesta de streaming
 */
export const parseStreamChunk = (data: string): string | null => {
  if (!data.startsWith('data: ')) return null

  const content = data.slice(6)
  if (content === '[DONE]') return null

  try {
    const json = JSON.parse(content)
    return json.choices?.[0]?.delta?.content || null
  } catch {
    return null
  }
}

/**
 * Formatea tokens para display
 */
export const formatTokens = (tokens: number): string => {
  if (tokens < 1000) return `${tokens}`
  return `${(tokens / 1000).toFixed(1)}k`
}

/**
 * Calcula duración estimada de respuesta
 */
export const estimateResponseTime = (tokens: number): string => {
  // Aproximadamente 40 tokens por segundo en streaming
  const seconds = Math.ceil(tokens / 40)
  if (seconds < 60) return `~${seconds}s`
  const minutes = Math.ceil(seconds / 60)
  return `~${minutes}m`
}

/**
 * Detecta si el mensaje contiene código
 */
export const hasCodeBlock = (text: string): boolean => {
  return /```[\s\S]*?```/.test(text)
}

/**
 * Extrae bloques de código de un mensaje
 */
export const extractCodeBlocks = (
  text: string
): Array<{ language: string; code: string }> => {
  const regex = /```(\w+)?\n([\s\S]*?)```/g
  const blocks: Array<{ language: string; code: string }> = []

  let match
  while ((match = regex.exec(text)) !== null) {
    blocks.push({
      language: match[1] || 'text',
      code: match[2].trim(),
    })
  }

  return blocks
}

/**
 * Convierte markdown a HTML simple (no usa librerías pesadas)
 */
export const simpleMarkdownToHtml = (text: string): string => {
  let html = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // bold
    .replace(/\*(.*?)\*/g, '<em>$1</em>') // italic
    .replace(/\n/g, '<br/>') // line breaks

  return html
}

/**
 * Detecta idioma del texto (básico)
 */
export const detectLanguage = (text: string): 'es' | 'en' | 'auto' => {
  // Palabras españolas comunes
  const spanishWords = ['el', 'la', 'de', 'que', 'y', 'para', 'con', 'por']
  const spanishMatches = spanishWords.filter((w) =>
    text.toLowerCase().includes(w)
  ).length

  // Palabras inglesas comunes
  const englishWords = ['the', 'is', 'and', 'or', 'for', 'with', 'to', 'a']
  const englishMatches = englishWords.filter((w) =>
    text.toLowerCase().includes(w)
  ).length

  if (spanishMatches > englishMatches) return 'es'
  if (englishMatches > spanishMatches) return 'en'
  return 'auto'
}

/**
 * Valida si el servidor OpenCode está disponible
 */
export const validateOpenCodeUrl = (url: string): boolean => {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}
