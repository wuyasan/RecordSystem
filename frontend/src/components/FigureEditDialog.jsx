import React, { useState } from "react";

export default function FigureEditDialog({ init, onSubmit, onClose }) {
  const [form, setForm] = useState({ ...init });

  const update = (k) => (e) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div className="dialog-mask" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <h3>编辑条目</h3>
        {["manufacturer", "brand", "character", "model_name", "ip"].map((k) => (
          <div key={k}>
            <label>{k}</label>
            <input value={form[k] || ""} onChange={update(k)} />
          </div>
        ))}
        <div>
          <label>成本价</label>
          <input type="number" value={form.cost_price}
                 onChange={update("cost_price")} />
        </div>
        <div>
          <label>库存</label>
          <input type="number" value={form.qty}
                 onChange={update("qty")} />
        </div>

        <button onClick={() => onSubmit(form)}>保存</button>
        <button onClick={onClose}>取消</button>
      </div>
    </div>
  );
}