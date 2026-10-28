import { createRoot } from 'react-dom/client';
import { LanguageProvider } from './lib/i18n';
import Home from './app/page';
import './app/globals.css';

createRoot(document.getElementById('root')!).render(<LanguageProvider><Home /></LanguageProvider>);
