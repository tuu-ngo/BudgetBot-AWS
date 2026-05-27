export const transactions = [
  {
    id: 't1',
    date: 'Nov 15',
    description: 'GRAB FOOD HCM',
    category: 'Food',
    amount: -120000,
    confidence: 'high',
  },
  {
    id: 't2',
    date: 'Nov 15',
    description: 'VINMART HCM 04',
    category: 'Groceries',
    amount: -340000,
    confidence: 'medium',
  },
  {
    id: 't3',
    date: 'Nov 14',
    description: 'NETFLIX.COM',
    category: 'Subscription',
    amount: -260000,
    confidence: 'high',
  },
  {
    id: 't4',
    date: 'Nov 14',
    description: 'SHOPEE PAY 8472',
    category: 'Shopping',
    amount: -890000,
    confidence: 'high',
  },
  {
    id: 't5',
    date: 'Nov 13',
    description: 'FT0024112501',
    category: 'Other',
    amount: -1500000,
    confidence: 'low',
    raw: 'Bank transfer code — unclear',
  },
  {
    id: 't6',
    date: 'Nov 13',
    description: 'GRAB CITY HCM',
    category: 'Food',
    amount: -65000,
    confidence: 'low',
    raw: 'Could be Transport or Food',
  },
  {
    id: 't7',
    date: 'Nov 12',
    description: 'SALARY NOV',
    category: 'Income',
    amount: 22000000,
    confidence: 'high',
  },
  {
    id: 't8',
    date: 'Nov 12',
    description: 'STARBUCKS NGUYEN HUE',
    category: 'Food',
    amount: -85000,
    confidence: 'high',
  },
  {
    id: 't9',
    date: 'Nov 11',
    description: 'POS*1234 MERCHANT',
    category: 'Other',
    amount: -450000,
    confidence: 'low',
    raw: 'Unknown POS terminal',
  },
  {
    id: 't10',
    date: 'Nov 11',
    description: 'SPOTIFY PREMIUM',
    category: 'Subscription',
    amount: -59000,
    confidence: 'high',
  },
  {
    id: 't11',
    date: 'Nov 10',
    description: 'BE TAXI HN',
    category: 'Transport',
    amount: -180000,
    confidence: 'high',
  },
  {
    id: 't12',
    date: 'Nov 10',
    description: 'CGV CINEMAS',
    category: 'Entertainment',
    amount: -220000,
    confidence: 'high',
  },
  {
    id: 't13',
    date: 'Nov 09',
    description: 'TRANSFER TO NGUYEN VAN A',
    category: 'Transfer',
    amount: -2000000,
    confidence: 'medium',
  },
  {
    id: 't14',
    date: 'Nov 08',
    description: 'VINFAST CHARGE',
    category: 'Transport',
    amount: -150000,
    confidence: 'medium',
  },
  {
    id: 't15',
    date: 'Nov 07',
    description: 'MACBOOK SHOPEE',
    category: 'Shopping',
    amount: -34000000,
    confidence: 'medium',
    raw: 'Personal or business?',
  },
]

export const categoryColors = {
  Food: '#F59E0B',
  Groceries: '#10B981',
  Shopping: '#8B5CF6',
  Subscription: '#3B82F6',
  Subscriptions: '#3B82F6',
  Transport: '#06B6D4',
  Utilities: '#14B8A6',
  Bills: '#6366F1',
  Entertainment: '#EC4899',
  Health: '#EF4444',
  Income: '#22C55E',
  Transfer: '#94A3B8',
  Other: '#71717A',
}

export const formatVND = (n) => {
  const formatted = new Intl.NumberFormat('en-US').format(Math.abs(n))
  return `${n < 0 ? '-' : ''}₫${formatted}`
}

export const confidencePill = (c) => {
  if (c === 'high')
    return { label: 'High', color: 'bg-green-100 text-green-700' }
  if (c === 'medium')
    return { label: 'Medium', color: 'bg-yellow-100 text-yellow-700' }
  return { label: 'Low', color: 'bg-red-100 text-red-700' }
}

export const categoryOptions = [
  'Food',
  'Groceries',
  'Shopping',
  'Subscriptions',
  'Transport',
  'Utilities',
  'Bills',
  'Entertainment',
  'Health',
  'Income',
  'Transfer',
  'Other',
]
