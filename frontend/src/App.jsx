import React from 'react'; 
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import FigureTable from './components/FigureTable'
import FigureForm from './components/FigureForm'
import './styles.css'

export default function App() {
  return (
    <BrowserRouter>
      <h1 className="title">📦 手办库存</h1>
      <Routes>
        <Route path="/" element={<FigureTable />} />
        <Route path="/new" element={<FigureForm />} />
      </Routes>
    </BrowserRouter>
  )
}