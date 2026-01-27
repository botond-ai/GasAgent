import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { ChatContainer } from './components/chat';
import Tickets from './pages/Tickets';
import Documents from './pages/Documents';
import './App.css';

function Navigation() {
  const location = useLocation();

  return (
    <nav className="main-nav">
      <div className="nav-container">
        <div className="nav-brand">
          <h1>SupportAI</h1>
          <span className="nav-subtitle">AI-Powered Support</span>
        </div>
        <ul className="nav-links">
          <li>
            <Link
              to="/"
              className={'nav-link' + (location.pathname === '/' ? ' active' : '')}
            >
              Chat
            </Link>
          </li>
          <li>
            <Link
              to="/tickets"
              className={'nav-link' + (location.pathname === '/tickets' ? ' active' : '')}
            >
              Tickets
            </Link>
          </li>
          <li>
            <Link
              to="/documents"
              className={'nav-link' + (location.pathname === '/documents' ? ' active' : '')}
            >
              Knowledge Base
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
}

function ChatPage() {
  return (
    <div className="chat-page">
      <ChatContainer />
    </div>
  );
}

function App() {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/tickets" element={<Tickets />} />
            <Route path="/documents" element={<Documents />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
