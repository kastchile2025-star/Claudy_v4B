import axios, { AxiosInstance } from 'axios'
import { OpenCodeResponse } from '../types'

class OpenCodeService {
  private axiosInstance: AxiosInstance

  constructor(baseURL: string = 'http://localhost:4096') {
    this.axiosInstance = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })
  }

  /**
   * Enviar mensaje a OpenCode y obtener respuesta
   */
  async sendMessage(
    prompt: string,
    options: {
      model?: string
      temperature?: number
      maxTokens?: number
      systemPrompt?: string
      stream?: boolean
    } = {}
  ): Promise<OpenCodeResponse> {
    try {
      const response = await this.axiosInstance.post('/chat/completions', {
        messages: [
          {
            role: 'system',
            content: options.systemPrompt || 'Eres un asistente IA útil',
          },
          {
            role: 'user',
            content: prompt,
          },
        ],
        model: options.model || 'deepseek/deepseek-chat',
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens || 2048,
        stream: options.stream || false,
      })

      return {
        response: response.data.choices[0].message.content,
        model: response.data.model,
        tokensUsed: response.data.usage?.total_tokens || 0,
        finishReason: response.data.choices[0].finish_reason,
      }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`OpenCode error: ${error.message}`)
      }
      throw error
    }
  }

  /**
   * Enviar mensaje con streaming
   */
  async sendMessageStream(
    prompt: string,
    onChunk: (chunk: string) => void,
    options: {
      model?: string
      temperature?: number
      maxTokens?: number
      systemPrompt?: string
    } = {}
  ): Promise<void> {
    try {
      const response = await this.axiosInstance.post(
        '/chat/completions',
        {
          messages: [
            {
              role: 'system',
              content: options.systemPrompt || 'Eres un asistente IA útil',
            },
            {
              role: 'user',
              content: prompt,
            },
          ],
          model: options.model || 'deepseek/deepseek-chat',
          temperature: options.temperature ?? 0.7,
          max_tokens: options.maxTokens || 2048,
          stream: true,
        },
        {
          responseType: 'stream',
        }
      )

      response.data.on('data', (chunk: Buffer) => {
        const text = chunk.toString()
        const lines = text.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.replace('data: ', '')
            if (data === '[DONE]') break

            try {
              const json = JSON.parse(data)
              const content = json.choices[0]?.delta?.content
              if (content) {
                onChunk(content)
              }
            } catch (e) {
              // Ignorar líneas malformadas
            }
          }
        }
      })
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`OpenCode stream error: ${error.message}`)
      }
      throw error
    }
  }

  /**
   * Listar modelos disponibles
   */
  async getModels(): Promise<any[]> {
    try {
      const response = await this.axiosInstance.get('/models')
      return response.data.data || []
    } catch (error) {
      console.error('Error fetching models:', error)
      return []
    }
  }

  /**
   * Verificar estado del servidor
   */
  async health(): Promise<boolean> {
    try {
      const response = await this.axiosInstance.get('/health')
      return response.status === 200
    } catch {
      return false
    }
  }

  /**
   * Ejecutar herramientas (read, write, exec)
   */
  async executeTool(
    tool: 'read' | 'write' | 'exec',
    params: Record<string, any>
  ): Promise<any> {
    try {
      const response = await this.axiosInstance.post('/tools/execute', {
        tool,
        params,
      })
      return response.data
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Tool execution error: ${error.message}`)
      }
      throw error
    }
  }

  /**
   * Búsqueda web
   */
  async webSearch(query: string): Promise<any[]> {
    try {
      const response = await this.axiosInstance.post('/search', { query })
      return response.data.results || []
    } catch (error) {
      console.error('Error in web search:', error)
      return []
    }
  }

  /**
   * Consultar memoria vectorial
   */
  async queryMemory(query: string, topK: number = 5): Promise<any[]> {
    try {
      const response = await this.axiosInstance.post('/memory/query', {
        query,
        top_k: topK,
      })
      return response.data.results || []
    } catch (error) {
      console.error('Error querying memory:', error)
      return []
    }
  }
}

export default new OpenCodeService()
