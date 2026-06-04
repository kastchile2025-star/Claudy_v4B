import { useState, useCallback } from 'react'
import openCodeService from '../services/opencode'

interface UseOpenCodeOptions {
  onChunk?: (chunk: string) => void
  onError?: (error: Error) => void
  onComplete?: (fullResponse: string) => void
}

export const useOpenCode = (options: UseOpenCodeOptions = {}) => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const sendMessage = useCallback(
    async (
      prompt: string,
      config: {
        model?: string
        temperature?: number
        maxTokens?: number
        systemPrompt?: string
      } = {}
    ) => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await openCodeService.sendMessage(prompt, {
          ...config,
          stream: false,
        })

        options.onComplete?.(response.response)
        return response
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err))
        setError(error)
        options.onError?.(error)
        throw error
      } finally {
        setIsLoading(false)
      }
    },
    [options]
  )

  const sendMessageStream = useCallback(
    async (
      prompt: string,
      config: {
        model?: string
        temperature?: number
        maxTokens?: number
        systemPrompt?: string
      } = {}
    ) => {
      setIsLoading(true)
      setError(null)

      try {
        let fullResponse = ''

        await openCodeService.sendMessageStream(
          prompt,
          (chunk) => {
            fullResponse += chunk
            options.onChunk?.(chunk)
          },
          config
        )

        options.onComplete?.(fullResponse)
        return fullResponse
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err))
        setError(error)
        options.onError?.(error)
        throw error
      } finally {
        setIsLoading(false)
      }
    },
    [options]
  )

  const checkHealth = useCallback(async () => {
    return await openCodeService.health()
  }, [])

  return {
    sendMessage,
    sendMessageStream,
    checkHealth,
    isLoading,
    error,
  }
}
