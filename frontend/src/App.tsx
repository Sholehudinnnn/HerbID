import React from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { HomePage } from './pages/HomePage';
import { SpeciesListPage } from './pages/SpeciesListPage';
import { SpeciesDetailPage } from './pages/SpeciesDetailPage';
import { SmartSearchPage } from './pages/SmartSearchPage';
import { RecipesListPage } from './pages/RecipesListPage';
import { RecipeDetailPage } from './pages/RecipeDetailPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { SourcesPage } from './pages/SourcesPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { AboutPage } from './pages/AboutPage';
import { NotFoundPage } from './pages/NotFoundPage';


export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-[#F8FAF8] text-[#1F2937]">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-[#166534] focus:text-white focus:rounded-xl focus:font-semibold"
        >
          Lewati ke konten utama
        </a>
        <Navbar />
        <main id="main-content" className="flex-1">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/search" element={<SmartSearchPage />} />
            <Route path="/recipes" element={<RecipesListPage />} />
            <Route path="/recipes/:slug" element={<RecipeDetailPage />} />
            <Route path="/species" element={<SpeciesListPage />} />
            <Route path="/species/:slug" element={<SpeciesDetailPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/sources" element={<SourcesPage />} />
            <Route path="/evaluation" element={<EvaluationPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="*" element={<NotFoundPage />} />

          </Routes>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  );
};

export default App;
