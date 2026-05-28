import React, { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload as UploadIcon,
  FileText,
  Check,
  Loader2,
  AlertCircle,
  AlertTriangle,
  X,
  ArrowRight,
  Info,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '../components/app/AppShell'
import { PillButton } from '../components/landing/PillButton'
import { api } from '../lib/api'
export function Upload() {
  const [status, setStatus] = useState('idle')
  const [file, setFile] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [uploadResult, setUploadResult] = useState(null)
  const [budgetCheck, setBudgetCheck] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)
  const navigate = useNavigate()
  const validateFile = (f) => {
    const validTypes = ['text/csv', 'application/vnd.ms-excel']
    const isCSV = f.name.toLowerCase().endsWith('.csv')
    if (!isCSV && !validTypes.includes(f.type)) {
      setErrorMsg('Invalid file format. Only CSV files are accepted.')
      setStatus('error')
      return false
    }
    if (f.size > 10 * 1024 * 1024) {
      setErrorMsg('File too large. Maximum size is 10MB.')
      setStatus('error')
      return false
    }
    return true
  }
  const handleFile = (f) => {
    setErrorMsg('')
    if (validateFile(f)) {
      setFile(f)
      setStatus('selected')
    }
  }
  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) handleFile(f)
  }
  const handleProcess = async () => {
    if (!file) return
    setErrorMsg('')
    setUploadResult(null)
    setBudgetCheck(null)
    try {
      setStatus('uploading')
      const result = await api.uploadStatement(file)
      setUploadResult(result)
      let latestBudgetCheck = result.budget_check || null

      if (result.flow_mode === 'aws' && result.file_id) {
        setStatus('processing')
        let latestStatus = result.status || 'pending'
        for (let i = 0; i < 20 && !['done', 'error'].includes(latestStatus); i += 1) {
          await new Promise((r) => setTimeout(r, 1500))
          const fileStatus = await api.getUploadStatus(result.file_id)
          latestStatus = fileStatus.status
        }
        if (latestStatus === 'error') {
          throw new Error('File processing failed. Please try another CSV.')
        }
        latestBudgetCheck = await api.checkBudget()
      }

      setBudgetCheck(latestBudgetCheck)
      setStatus('success')
      if (!latestBudgetCheck?.warnings_count) {
        setTimeout(() => navigate('/dashboard'), 1500)
      }
    } catch (err) {
      setErrorMsg(err.message || 'Upload failed. Please try again.')
      setStatus('error')
    }
  }
  const reset = () => {
    setFile(null)
    setStatus('idle')
    setErrorMsg('')
    setUploadResult(null)
    setBudgetCheck(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }
  const budgetWarnings = budgetCheck?.warnings || []
  return (
    <AppShell
      title="Upload Statement"
      subtitle="Upload your bank statement to start analyzing your finances with AI."
    >
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Upload Card */}
        <div className="lg:col-span-2">
          <motion.div
            initial={{
              opacity: 0,
              y: 20,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            className="bg-white rounded-3xl border border-gray-100 shadow-card p-8"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) =>
                e.target.files?.[0] && handleFile(e.target.files[0])
              }
            />

            <AnimatePresence mode="wait">
              {status === 'idle' || status === 'error' ? (
                <motion.div
                  key="dropzone"
                  initial={{
                    opacity: 0,
                  }}
                  animate={{
                    opacity: 1,
                  }}
                  exit={{
                    opacity: 0,
                  }}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragOver(true)
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  className={`border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all ${dragOver ? 'border-orange-500 bg-orange-50 scale-[1.01]' : 'border-gray-200 hover:border-orange-400 hover:bg-orange-50/30'}`}
                >
                  <motion.div
                    animate={
                      dragOver
                        ? {
                            y: -8,
                          }
                        : {
                            y: 0,
                          }
                    }
                    className="w-16 h-16 rounded-2xl bg-black text-white flex items-center justify-center mx-auto mb-5"
                  >
                    <UploadIcon size={24} />
                  </motion.div>
                  <p className="text-lg font-semibold text-gray-900 mb-1">
                    {dragOver
                      ? 'Drop your file here'
                      : 'Drag & drop your CSV file'}
                  </p>
                  <p className="text-sm text-gray-500 mb-5">
                    or click to browse from your computer
                  </p>
                  <div className="inline-block">
                    <PillButton className="text-xs">Choose file</PillButton>
                  </div>
                  <p className="text-[11px] text-gray-400 mt-5">
                    CSV files only · Max 10MB
                  </p>
                </motion.div>
              ) : (
                <motion.div
                  key="file"
                  initial={{
                    opacity: 0,
                    scale: 0.98,
                  }}
                  animate={{
                    opacity: 1,
                    scale: 1,
                  }}
                  exit={{
                    opacity: 0,
                  }}
                  className="border border-gray-100 rounded-2xl p-8"
                >
                  {/* File info */}
                  <div className="flex items-center gap-4 mb-6">
                    <div className="w-12 h-12 rounded-xl bg-orange-100 text-orange-600 flex items-center justify-center flex-shrink-0">
                      <FileText size={20} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-gray-900 truncate">
                        {file?.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {file && (file.size / 1024).toFixed(1)} KB · CSV
                      </p>
                    </div>
                    {status === 'selected' && (
                      <button
                        onClick={reset}
                        className="w-9 h-9 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500"
                        title="Remove file"
                      >
                        <X size={16} />
                      </button>
                    )}
                  </div>

                  {/* Status feedback */}
                  <AnimatePresence mode="wait">
                    {status === 'uploading' && (
                      <motion.div
                        key="uploading"
                        initial={{
                          opacity: 0,
                          y: 10,
                        }}
                        animate={{
                          opacity: 1,
                          y: 0,
                        }}
                        exit={{
                          opacity: 0,
                        }}
                        className="bg-blue-50 border border-blue-100 rounded-xl p-4 mb-6 flex items-center gap-3"
                      >
                        <Loader2
                          size={16}
                          className="text-blue-600 animate-spin flex-shrink-0"
                        />
                        <div className="flex-1">
                          <p className="text-sm font-medium text-blue-900">
                            Uploading file...
                          </p>
                          <div className="h-1 bg-blue-100 rounded-full overflow-hidden mt-2">
                            <motion.div
                              initial={{
                                width: '0%',
                              }}
                              animate={{
                                width: '85%',
                              }}
                              transition={{
                                duration: 1.2,
                              }}
                              className="h-full bg-blue-500 rounded-full"
                            />
                          </div>
                        </div>
                      </motion.div>
                    )}
                    {status === 'processing' && (
                      <motion.div
                        key="processing"
                        initial={{
                          opacity: 0,
                          y: 10,
                        }}
                        animate={{
                          opacity: 1,
                          y: 0,
                        }}
                        exit={{
                          opacity: 0,
                        }}
                        className="bg-orange-50 border border-orange-100 rounded-xl p-4 mb-6 flex items-center gap-3"
                      >
                        <Loader2
                          size={16}
                          className="text-orange-600 animate-spin flex-shrink-0"
                        />
                        <div className="flex-1">
                          <p className="text-sm font-medium text-orange-900">
                            AI processing transactions...
                          </p>
                          <p className="text-xs text-orange-700 mt-0.5">
                            Classifying with Claude Haiku · Detecting categories
                          </p>
                        </div>
                      </motion.div>
                    )}
                    {status === 'success' && (
                      <motion.div
                        key="success"
                        initial={{
                          opacity: 0,
                          y: 10,
                        }}
                        animate={{
                          opacity: 1,
                          y: 0,
                        }}
                        exit={{
                          opacity: 0,
                        }}
                        className="bg-green-50 border border-green-100 rounded-xl p-4 mb-6 flex items-center gap-3"
                      >
                        <div className="w-7 h-7 rounded-full bg-green-500 text-white flex items-center justify-center flex-shrink-0">
                          <Check size={14} />
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-green-900">
                            Processed successfully!
                          </p>
                          <p className="text-xs text-green-700 mt-0.5">
                            {uploadResult?.rows_inserted ?? 0} transactions classified
                            {uploadResult?.rows_review
                              ? ` · ${uploadResult.rows_review} need review`
                              : ''}{' '}
                            {budgetWarnings.length
                              ? '· Budget warning detected'
                              : '· Redirecting to dashboard...'}
                          </p>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {status === 'success' && budgetWarnings.length > 0 && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-red-50 border border-red-100 rounded-xl p-4 mb-6"
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-red-500 text-white flex items-center justify-center flex-shrink-0">
                          <AlertTriangle size={16} />
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-semibold text-red-900">
                            Budget cap exceeded
                          </p>
                          <p className="text-xs text-red-700 mt-0.5">
                            Your latest upload pushed one or more categories over budget.
                          </p>
                          <div className="mt-3 space-y-2">
                            {budgetWarnings.map((warning) => (
                              <div
                                key={warning.category}
                                className="bg-white/70 border border-red-100 rounded-lg p-3 text-xs text-red-900"
                              >
                                <div className="flex items-center justify-between gap-3">
                                  <span className="font-semibold">{warning.category}</span>
                                  <span>{warning.percent}% used</span>
                                </div>
                                <p className="mt-1 text-red-700">
                                  Spent {Number(warning.spent).toLocaleString()} / cap{' '}
                                  {Number(warning.cap_amount).toLocaleString()} · over by{' '}
                                  {Number(warning.over_by).toLocaleString()}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}

                  {/* Actions */}
                  {status === 'selected' && (
                    <div className="flex items-center gap-3">
                      <button
                        onClick={reset}
                        className="px-5 py-2.5 rounded-full text-xs font-medium text-gray-600 hover:bg-gray-100"
                      >
                        Cancel
                      </button>
                      <PillButton
                        onClick={handleProcess}
                        className="flex-1 sm:flex-none"
                      >
                        Process file
                      </PillButton>
                    </div>
                  )}
                  {status === 'success' && (
                    <button
                      onClick={() => navigate('/dashboard')}
                      className="text-xs font-medium text-orange-600 hover:text-orange-700 flex items-center gap-1"
                    >
                      Go to dashboard <ArrowRight size={12} />
                    </button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error message */}
            <AnimatePresence>
              {errorMsg && (
                <motion.div
                  initial={{
                    opacity: 0,
                    y: -5,
                  }}
                  animate={{
                    opacity: 1,
                    y: 0,
                  }}
                  exit={{
                    opacity: 0,
                  }}
                  className="mt-4 flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-3"
                >
                  <AlertCircle size={14} />
                  {errorMsg}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>

        {/* Guide */}
        <motion.div
          initial={{
            opacity: 0,
            y: 20,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            delay: 0.1,
          }}
          className="bg-black text-white rounded-3xl p-6 relative overflow-hidden h-fit"
        >
          <div className="absolute -right-10 -top-10 w-32 h-32 rounded-full bg-orange-500/20 blur-2xl" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-4">
              <Info size={14} className="text-orange-400" />
              <span className="text-[10px] uppercase tracking-widest text-orange-400 font-bold">
                CSV Format Guide
              </span>
            </div>
            <h3 className="font-bold mb-3">Accepted format</h3>
            <p className="text-xs text-gray-400 leading-relaxed mb-5">
              Upload bank statements exported as CSV from Vietcombank, MB Bank,
              Techcombank, or similar banks.
            </p>
            <div className="space-y-3">
              <p className="text-[10px] uppercase tracking-wider text-gray-500 font-bold">
                Required columns
              </p>
              {[
                {
                  col: 'date',
                  desc: 'Transaction date',
                },
                {
                  col: 'description',
                  desc: 'Transaction details',
                },
                {
                  col: 'amount',
                  desc: 'Negative = expense',
                },
              ].map((c) => (
                <div key={c.col} className="flex items-center gap-3 text-xs">
                  <code className="bg-white/10 text-orange-400 px-2 py-0.5 rounded font-mono">
                    {c.col}
                  </code>
                  <span className="text-gray-400">{c.desc}</span>
                </div>
              ))}
            </div>
            <div className="mt-6 pt-5 border-t border-white/10 text-[11px] text-gray-500 leading-relaxed">
              💡 Tip: AI will automatically classify transactions into
              categories like Food, Shopping, Transport, etc.
            </div>
          </div>
        </motion.div>
      </div>
    </AppShell>
  )
}
