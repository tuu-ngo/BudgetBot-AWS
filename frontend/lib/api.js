const DEFAULT_USER_ID = '00000000-0000-0000-0000-000000000001'

const getApiBaseUrl = () => {
  const fromEnv = import.meta.env.VITE_API_BASE_URL
  if (fromEnv) return fromEnv.replace(/\/$/, '')
  return window.location.port === '5173' ? 'http://localhost:8000' : ''
}

const API_BASE_URL = getApiBaseUrl()

async function request(path, options = {}) {
  const headers = {
    'X-User-Id': DEFAULT_USER_ID,
    ...(options.headers || {}),
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body:
      options.body && !(options.body instanceof FormData)
        ? JSON.stringify(options.body)
        : options.body,
  })

  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    const message = data?.detail || data?.message || data || 'Request failed'
    throw new Error(message)
  }

  return data
}

export const api = {
  health: () => request('/health'),
  uploadStatement: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request('/upload', {
      method: 'POST',
      body: formData,
    })
  },
  getUploadStatus: (fileId) => request(`/upload/${fileId}/status`),
  getFiles: () => request('/files'),
  getSummary: (month) => request(`/summary${month ? `?month=${month}` : ''}`),
  getTransactions: ({ month, reviewStatus } = {}) => {
    const params = new URLSearchParams()
    if (month) params.set('month', month)
    if (reviewStatus) params.set('review_status', reviewStatus)
    const query = params.toString()
    return request(`/transactions${query ? `?${query}` : ''}`)
  },
  getReviewTransactions: () => request('/transactions/review'),
  updateTransactionCategory: (transactionId, category) =>
    request(`/transactions/${transactionId}/category`, {
      method: 'PATCH',
      body: { category },
    }),
  getBudgetCaps: () => request('/budget-caps'),
  checkBudget: () => request('/budget/check', { method: 'POST' }),
  setBudgetCap: (category, capAmount) =>
    request(`/budget-caps/${encodeURIComponent(category)}`, {
      method: 'PUT',
      body: { cap_amount: Number(capAmount) },
    }),
  chat: (message, month) =>
    request('/chat', {
      method: 'POST',
      body: { message, month },
    }),
  getChatHistory: (limit = 50) => request(`/chat/history?limit=${limit}`),
}

export const normalizeTransaction = (txn) => ({
  id: txn.transaction_id || txn.id,
  transaction_id: txn.transaction_id || txn.id,
  file_id: txn.file_id,
  date: txn.time ? new Date(txn.time).toLocaleDateString('en-US', {
    month: 'short',
    day: '2-digit',
  }) : '',
  rawDate: txn.time || txn.date || '',
  description: txn.description || '',
  category: txn.category || 'Other',
  amount: Number(txn.amount || 0),
  confidence:
    Number(txn.confident || 0) >= 0.8
      ? 'high'
      : Number(txn.confident || 0) >= 0.6
        ? 'medium'
        : 'low',
  confident: Number(txn.confident || 0),
  review_status: txn.review_status || 'ok',
})

export const getApiConfig = () => ({
  baseUrl: API_BASE_URL || window.location.origin,
})
