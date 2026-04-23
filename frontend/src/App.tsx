import { createBrowserRouter, RouterProvider } from 'react-router-dom'

import ProtectedRoute from './components/ProtectedRoute'
import AppShell from './routes/AppShell'
import ConversationPage from './routes/ConversationPage'
import Home from './routes/Home'
import AuditPage from './routes/AuditPage'
import LoginPage from './routes/LoginPage'
import ScheduledPage from './routes/ScheduledPage'
import TodosPage from './routes/TodosPage'
import VaultPage from './routes/VaultPage'

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <AppShell />,
        children: [
          { index: true, element: <Home /> },
          { path: 'conversations/:id', element: <ConversationPage /> },
          { path: 'todos', element: <TodosPage /> },
          { path: 'files', element: <VaultPage /> },
          { path: 'scheduled', element: <ScheduledPage /> },
          { path: 'audit', element: <AuditPage /> },
        ],
      },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
