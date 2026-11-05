import { useState } from 'react';
import { incrementCount } from './counter';
import './style.css';

export function App() {
  const [count, setCount] = useState(0);

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="React starter home">
          <span className="brand-mark" aria-hidden="true">R</span>
          <span>Frontend starter</span>
        </a>
        <span className="status"><span className="status-dot" /> Ready to explore</span>
      </header>

      <section className="hero" aria-labelledby="welcome-title">
        <p className="eyebrow">YOUR NEW CANVAS</p>
        <h1 id="welcome-title">A little space<br />to make something.</h1>
        <p className="intro">
          Your React frontend is up and running. Change the code, save, and watch
          your browser update.
        </p>

        <div className="demo-card">
          <div className="demo-copy">
            <p className="card-label">INTERACTIVE PREVIEW</p>
            <h2>One small step</h2>
            <p>Press the button and see your first state update.</p>
          </div>
          <div className="counter-row">
            <output className="counter-value" aria-live="polite" aria-label="Demo count">
              {count}
            </output>
            <button
              className="counter-button"
              type="button"
              onClick={() => setCount(incrementCount(count))}
            >
              Add a step <span aria-hidden="true">↗</span>
            </button>
          </div>
        </div>
      </section>

      <footer className="footer">
        <span>Built for your next idea.</span>
        <span>React · TypeScript · Vite</span>
      </footer>
    </main>
  );
}
