import React, { useRef, useState } from "react";
import { createFigure } from "../api";
import { useNavigate } from "react-router-dom";

export default function FigureForm() {
  const nav = useNavigate();
  const ref = useRef();
  const [qty, setQty] = useState(1);          // 首次入库数量

  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData(ref.current);
    fd.append("quantity", qty);               // 追加数量
    try {
      await createFigure(fd);
      nav("/");                              // 成功后返回主页
    } catch (err) {
      alert(err.response?.data?.detail || "保存失败");
    }
  };

  return (
    <form ref={ref} onSubmit={submit} className="fig-form">
      <input name="manufacturer" placeholder="厂家"     required />
      <input name="brand"        placeholder="品牌"     required />
      <input name="character"    placeholder="角色"     required />
      <input name="model_name"   placeholder="造型"     required />
      <input name="cost_price"   placeholder="成本价"  type="number" step="0.01" required />
      <input name="ip"           placeholder="作品名 (IP)" />
      
      <label>
        入库数量
        <input
          type="number"
          min="1"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          required
        />
      </label>

      <input name="image" type="file" accept="image/*" />
      <button type="submit">保存</button>
    </form>
  );
}