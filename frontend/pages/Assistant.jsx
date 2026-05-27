import React, { useEffect, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send,
  Bot,
  Sparkles,
  TrendingDown,
  DollarSign,
  PieChart,
} from 'lucide-react'
import { AppShell } from '../components/app/AppShell'
import { api } from '../lib/api'
const initialMessages = [
  {
    id: 'm1',
    role: 'ai',
    content:
      "Hi there! I'm your AI Money Coach. I've analyzed your November statement. Feel free to ask me anything about your finances.",
  },
]
const suggestedQuestions = [
  {
    icon: TrendingDown,
    text: 'How much did I spend on food this month?',
  },
  {
    icon: DollarSign,
    text: 'What was my biggest expense?',
  },
  {
    icon: PieChart,
    text: 'Am I overspending?',
  },
]
export function Assistant() {
  const [messages, setMessages] = useState(initialMessages)
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [error, setError] = useState('')
  const scrollRef = useRef(null)
  useEffect(() => {
    let active = true
    api
      .getChatHistory(20)
      .then((data) => {
        if (!active) return
        const history = [...(data.history || [])].reverse()
        if (!history.length) return
        setMessages(
          history.flatMap((entry) => [
            {
              id: `u-${entry.chat_history_id}`,
              role: 'user',
              content: entry.input,
            },
            {
              id: `a-${entry.chat_history_id}`,
              role: 'ai',
              content: entry.output,
            },
          ]),
        )
      })
      .catch((err) => {
        if (active) setError(err.message || 'Could not load chat history.')
      })
    return () => {
      active = false
    }
  }, [])
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages, thinking])
  const send = async (text) => {
    const content = text || input.trim()
    if (!content) return
    const userMsg = {
      id: `u${Date.now()}`,
      role: 'user',
      content,
    }
    setMessages((m) => [...m, userMsg])
    setInput('')
    setThinking(true)
    setError('')
    try {
      const resp = await api.chat(content)
      setMessages((m) => [
        ...m,
        {
          id: resp.chat_history_id || `a${Date.now()}`,
          role: 'ai',
          content: resp.output || 'No response returned.',
        },
      ])
    } catch (err) {
      setError(err.message || 'Could not send message.')
      setMessages((m) => m.filter((msg) => msg.id !== userMsg.id))
    } finally {
      setThinking(false)
    }
  }
  const renderContent = (text) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g)
    return parts.map((p, i) => {
      if (p.startsWith('**') && p.endsWith('**')) {
        return (
          <strong key={i} className="font-semibold text-orange-600">
            {p.slice(2, -2)}
          </strong>
        )
      }
      return <span key={i}>{p}</span>
    })
  }
  return (
    <AppShell
      title="AI Financial Assistant"
      subtitle="Your personal AI coach to help you understand your finances through natural conversation."
    >
      <div className="bg-white rounded-3xl border border-gray-100 shadow-card overflow-hidden flex flex-col h-[70vh]">
        {/* Header */}
        <div className="p-5 border-b border-gray-100 flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-full bg-black text-orange-400 flex items-center justify-center">
              <Bot size={18} />
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-green-500 border-2 border-white" />
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-sm">Money Coach AI</h3>
            <p className="text-xs text-gray-500 flex items-center gap-1">
              <Sparkles size={10} className="text-orange-500" /> Claude Haiku ·
              Online
            </p>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <motion.div
                key={m.id}
                initial={{
                  opacity: 0,
                  y: 10,
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                }}
                className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs ${m.role === 'user' ? 'bg-gradient-to-br from-orange-400 to-amber-600 text-white font-bold' : 'bg-black text-orange-400'}`}
                >
                  {m.role === 'user' ? 'T' : <Bot size={14} />}
                </div>
                <div
                  className={`max-w-[80%] ${m.role === 'user' ? 'items-end' : ''}`}
                >
                  <div
                    className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${m.role === 'user' ? 'bg-black text-white rounded-tr-sm' : 'bg-cream text-gray-800 rounded-tl-sm'}`}
                  >
                    {renderContent(m.content)}
                  </div>
                  {m.insight && (
                    <motion.div
                      initial={{
                        opacity: 0,
                        y: 10,
                      }}
                      animate={{
                        opacity: 1,
                        y: 0,
                      }}
                      transition={{
                        delay: 0.3,
                      }}
                      className="mt-2 grid grid-cols-3 gap-2"
                    >
                      {m.insight.map((ins, i) => (
                        <div
                          key={i}
                          className="bg-white border border-gray-100 rounded-xl p-2.5"
                        >
                          <p className="text-[10px] text-gray-500 uppercase tracking-wider">
                            {ins.label}
                          </p>
                          <p className="text-xs font-bold text-gray-900 mt-0.5">
                            {ins.value}
                          </p>
                        </div>
                      ))}
                    </motion.div>
                  )}
                </div>
              </motion.div>
            ))}
            {thinking && (
              <motion.div
                initial={{
                  opacity: 0,
                }}
                animate={{
                  opacity: 1,
                }}
                exit={{
                  opacity: 0,
                }}
                className="flex gap-3"
              >
                <div className="w-8 h-8 rounded-full bg-black text-orange-400 flex items-center justify-center">
                  <Bot size={14} />
                </div>
                <div className="bg-cream rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1">
                  {[0, 0.2, 0.4].map((d) => (
                    <motion.div
                      key={d}
                      animate={{
                        y: [0, -4, 0],
                      }}
                      transition={{
                        duration: 0.8,
                        repeat: Infinity,
                        delay: d,
                      }}
                      className="w-1.5 h-1.5 rounded-full bg-gray-400"
                    />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Suggested Questions */}
        {messages.length === 1 && (
          <div className="px-6 pb-3 flex flex-wrap gap-2">
            {suggestedQuestions.map((q, i) => (
              <motion.button
                key={i}
                initial={{
                  opacity: 0,
                  y: 10,
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                }}
                transition={{
                  delay: 0.3 + i * 0.1,
                }}
                whileHover={{
                  scale: 1.02,
                }}
                onClick={() => send(q.text)}
                className="flex items-center gap-2 text-xs px-3 py-2 rounded-full bg-cream border border-gray-100 hover:border-orange-400 hover:bg-orange-50 transition-colors"
              >
                <q.icon size={12} className="text-orange-500" />
                {q.text}
              </motion.button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="p-4 border-t border-gray-100">
          {error && (
            <div className="mb-3 rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-xs font-medium text-red-700">
              {error}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              send()
            }}
            className="flex items-center gap-2 bg-cream rounded-full p-1.5 pl-5"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about spending, budgets, savings..."
              className="flex-1 bg-transparent outline-none text-sm placeholder-gray-400"
            />
            <motion.button
              whileTap={{
                scale: 0.95,
              }}
              type="submit"
              disabled={!input.trim() || thinking}
              className="w-9 h-9 rounded-full bg-black text-white flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send size={14} />
            </motion.button>
          </form>
        </div>
      </div>
    </AppShell>
  )
}
