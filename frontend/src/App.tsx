import { createBrowserRouter, RouterProvider } from 'react-router-dom'

import ProtectedRoute from './components/ProtectedRoute'
import AppShell from './routes/AppShell'
import ConversationPage from './routes/ConversationPage'
import Home from './routes/Home'
import LoginPage from './routes/LoginPage'

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
        ],
      },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
