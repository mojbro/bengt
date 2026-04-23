import { createBrowserRouter, RouterProvider } from 'react-router-dom'

import ProtectedRoute from './components/ProtectedRoute'
import AppShell from './routes/AppShell'
import ConversationPage from './routes/ConversationPage'
import Home from './routes/Home'
import LoginPage from './routes/LoginPage'
import ScheduledPage from './routes/ScheduledPage'
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
          { path: 'files', element: <VaultPage /> },
          { path: 'scheduled', element: <ScheduledPage /> },
        ],
      },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
