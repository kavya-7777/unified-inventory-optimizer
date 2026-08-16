import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [health, setHealth] = useState<string>('checking...')
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  useEffect(() => {
    fetch(`${apiUrl}/health`)
      .then(res => res.json())
      .then(data => setHealth(data.status))
      .catch(err => setHealth(`error: ${err.message}`))
  }, [apiUrl])

  return (
    <div className="App">
      <h1>MEIO Platform Dashboard</h1>
      <div className="card">
        <p>
          Backend Status: <strong>{health}</strong>
        </p>
      </div>
      <p className="read-the-docs">
        FastAPI + React Integration Active
      </p>
    </div>
  )
}

export default App
