import React, { useEffect, useState, useMemo, useRef } from "react";
import {
  getFigures,
  deleteFigure,
  inbound,
  outbound,
  updateFigure,
  api,
} from "../api";
import { Link } from "react-router-dom";
import MovementDialog from "./MovementDialog";

/* ───────── 简易编辑弹窗 ───────── */
function EditDialog({ init, onSubmit, onClose }) {
  const [form, setForm] = useState({ ...init });
  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
  const clickStartedOnMask = useRef(false);

  return (
    <div
      className="dialog-mask"
      onMouseDown={(e) => (clickStartedOnMask.current = e.target === e.currentTarget)}
      onMouseUp={(e) =>
        clickStartedOnMask.current && e.target === e.currentTarget && onClose()
      }
    >
      <div className="dialog" onMouseDown={(e) => e.stopPropagation()}>
        <h3>编辑条目</h3>
        {["manufacturer", "brand", "character", "model_name", "ip"].map((k) => (
          <p key={k}>
            <label>{k}</label>
            <input value={form[k] || ""} onChange={set(k)} />
          </p>
        ))}
        <p>
          <label>成本价</label>
          <input type="number" value={form.cost_price} onChange={set("cost_price")} />
        </p>
        <p>
          <label>库存</label>
          <input type="number" value={form.qty} onChange={set("qty")} />
        </p>
        <button onClick={() => onSubmit(form)}>保存</button>
        <button onClick={onClose}>取消</button>
      </div>
    </div>
  );
}

/* ───────── 主表组件 ───────── */
export default function FigureTable() {
  /* ---------- 状态 ---------- */
  const [rows, setRows]     = useState([]);
  const [sel, setSel]       = useState({});
  const [dialog, setDialog] = useState(null);        // MovementDialog
  const [edit, setEdit]     = useState(null);        // EditDialog
  const [expanded, setExpanded] = useState(null);    // 明细
  const [sales, setSales]   = useState({});
  const [zoomId, setZoomId] = useState(null);
  const [compact, setCompact] = useState(false);     // ← 视图切换

  /* ---------- 加载 ---------- */
  const reload = async () => {
    const res = await getFigures();
    setRows(res.data);
  };
  useEffect(() => { reload(); }, []);

  /* ---------- 唯一选项 ---------- */
  const options = useMemo(() => {
    const uniq = (k) => [...new Set(rows.map((r) => r[k]).filter(Boolean))].sort();
    return {
      manufacturer: uniq("manufacturer"),
      brand: uniq("brand"),
      character: uniq("character"),
      model_name: uniq("model_name"),
      ip: uniq("ip"),
    };
  }, [rows]);

  /* ---------- 过滤 ---------- */
  const filtered = useMemo(
    () =>
      rows.filter(
        (r) =>
          (!sel.manufacturer || r.manufacturer === sel.manufacturer) &&
          (!sel.brand        || r.brand        === sel.brand) &&
          (!sel.character    || r.character    === sel.character) &&
          (!sel.model_name   || r.model_name   === sel.model_name) &&
          (!sel.ip           || r.ip           === sel.ip)
      ),
    [rows, sel]
  );

  /* ---------- 库存总量 ---------- */
  const totalQty = useMemo(
    () => filtered.reduce((acc, r) => acc + r.qty, 0),
    [filtered]
  );

  /* ---------- 明细 ---------- */
  const fetchSales = async (id) => {
    const res = await api.get(`/figures/${id}/sales`);
    setSales((p) => ({ ...p, [id]: res.data }));
  };

  /* ---------- 删除 ---------- */
  const del = async (id) => {
    if (!confirm("确定删除？")) return;
    await deleteFigure(id);
    reload();
  };

  /* ---------- 入 / 出库 ---------- */
  const move = async (id, type, qty, price = null) => {
    const fn = type === "IN" ? inbound : outbound;
    await fn({ figure_id: id, quantity: qty, sale_price: price });
    await reload();
    if (type === "OUT" && expanded === id) await fetchSales(id);
  };

  /* ---------- 折叠 ---------- */
  const toggle = async (id) => {
    if (expanded === id) return setExpanded(null);
    if (!sales[id]) await fetchSales(id);
    setExpanded(id);
  };

  /* ---------- 列表渲染辅助 ---------- */
  const renderFullRow = (r) => (
    <>
      <td>
        {r.image_url && (
          <img
            src={r.image_url}
            className={zoomId === r.id ? "zoomed" : ""}
            onClick={() => setZoomId(zoomId === r.id ? null : r.id)}
          />
        )}
      </td>
      <td>{r.manufacturer}</td>
      <td>{r.brand}</td>
      <td>{r.character}</td>
      <td>{r.model_name}</td>
      <td>{r.ip || "-"}</td>
      <td>{r.cost_price}</td>
      <td>{r.qty}</td>
      <td>{r.total_sales.toFixed(2)}</td>
      <td>
        <button onClick={() => toggle(r.id)}>
          {expanded === r.id ? "收起" : "明细"}
        </button>
        <button onClick={() => setDialog({ id: r.id, type: "IN" })}>入库</button>
        <button onClick={() => setDialog({ id: r.id, type: "OUT" })}>出库</button>
        <button onClick={() => setEdit(r)}>✏️ 编辑</button>
        <button onClick={() => del(r.id)}>删除</button>
      </td>
    </>
  );

  const renderCompactRow = (r) => (
    <>
      <td>
        {r.image_url && (
          <img
            src={r.image_url}
            className={zoomId === r.id ? "zoomed" : ""}
            onClick={() => setZoomId(zoomId === r.id ? null : r.id)}
          />
        )}
      </td>
      <td>{r.character}</td>
      <td>{r.model_name}</td>
      <td>{r.ip || "-"}</td>
      <td>{r.qty}</td>
      <td>
        <button onClick={() => setDialog({ id: r.id, type: "OUT" })}>出库</button>
        <button onClick={() => del(r.id)}>删除</button>
      </td>
    </>
  );

  /* ---------- 视图相关表头 ---------- */
  const theadFull = (
    <tr>
      <th>图片</th><th>厂家</th><th>品牌</th><th>角色</th><th>造型</th><th>IP</th>
      <th>成本</th><th>库存</th><th>总销售额</th><th>操作</th>
    </tr>
  );
  const theadCompact = (
    <tr>
      <th>图片</th><th>角色</th><th>造型</th><th>IP</th><th>库存</th><th>操作</th>
    </tr>
  );

  /* ---------- 渲染 ---------- */
  return (
    <>
      {/* ───────── 工具栏 ───────── */}
      <div className="toolbar">
        <Link to="/new">➕ 新增</Link>
        {["manufacturer","brand","character","model_name","ip"].map((k) => (
          <select key={k}
                  value={sel[k] || ""}
                  onChange={(e) => setSel((p) => ({ ...p, [k]: e.target.value || undefined }))}>
            <option value="">{k}</option>
            {options[k].map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        ))}
        <button onClick={() => setSel({})}>清空</button>
        <button onClick={() => setCompact((v) => !v)}>
          {compact ? "切到完整视图" : "切到简洁视图"}
        </button>
      </div>

      <div className="totals-bar">
        <strong>库存总量：</strong>{totalQty}
      </div>

      {/* ───────── 表格 ───────── */}
      <table className="fig-table">
        <thead>{compact ? theadCompact : theadFull}</thead>
        <tbody>
          {filtered.map((r) => (
            <React.Fragment key={r.id}>
              <tr>{compact ? renderCompactRow(r) : renderFullRow(r)}</tr>

              {/* 明细只在完整视图里出现 */}
              {!compact && expanded === r.id && (
                <tr className="sales-row">
                  <td colSpan={10}>
                    <table className="sales-table">
                      <thead>
                        <tr><th>单价</th><th>数量</th><th>总价</th><th>出售时间</th></tr>
                      </thead>
                      <tbody>
                        {sales[r.id]?.length ? (
                          sales[r.id].map((s,i)=>(
                            <tr key={i}>
                              <td>{(+s.sale_price).toFixed(2)}</td>
                              <td>{s.quantity}</td>
                              <td>{(+s.sale_price * s.quantity).toFixed(2)}</td>
                              <td>{new Date(s.moved_at).toLocaleString()}</td>
                            </tr>
                          ))
                        ) : (
                          <tr><td colSpan={4}>暂无销售记录</td></tr>
                        )}
                      </tbody>
                    </table>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>

      {/* ───────── 入/出库弹窗 ───────── */}
      {dialog && (
        <MovementDialog
          type={dialog.type}
          onSubmit={(qty, price) => {
            move(dialog.id, dialog.type, qty, price);
            setDialog(null);
          }}
          onClose={() => setDialog(null)}
        />
      )}

      {/* ───────── 编辑弹窗 ───────── */}
      {edit && (
        <EditDialog
          init={edit}
          onSubmit={async (data) => {
            await updateFigure(edit.id, data);
            await reload();
            setEdit(null);
            if (expanded === edit.id) await fetchSales(edit.id);
          }}
          onClose={() => setEdit(null)}
        />
      )}
    </>
  );
}