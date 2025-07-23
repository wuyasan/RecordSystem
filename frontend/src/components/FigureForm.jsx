import React from 'react'; 
import { useRef } from 'react'
import { createFigure } from '../api'
import { useNavigate } from 'react-router-dom'

export default function FigureForm() {
  const nav = useNavigate()
  const ref = useRef()

  const submit = (e) => {
    e.preventDefault()
    const fd = new FormData(ref.current)
    createFigure(fd).then(()=>nav('/'))
  }

  return (
    <form ref={ref} onSubmit={submit} className="fig-form">
      {/* 每个输入 name 与后端参数一致 */}
      <input name="manufacturer" placeholder="厂家" required />
      <input name="brand" placeholder="品牌" required />
      <input name="character" placeholder="角色" required />
      <input name="model_name" placeholder="造型" required />
      <input name="cost_price" placeholder="成本价" type="number" step="0.01" required />
      <input name="ip" placeholder="作品名" type="text"/>
      <input name="image" type="file" accept="image/*" />
      <button type="submit">保存</button>
    </form>
  )
}