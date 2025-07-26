import React, { useEffect, useState, useMemo } from "react";
import { getFigures, deleteFigure, inbound, outbound, api } from "../api";
import { Link } from "react-router-dom";
import MovementDialog from "./MovementDialog";

export default function FigureTable() {
  /* ---------- 状态 ---------- */
  const [rows,    setRows]    = useState([]);
  const [sel,     setSel]     = useState({});      // 当前筛选
  const [dialog,  setDialog]  = useState(null);    // { id, type }
  const [expanded,setExpanded]= useState(null);    // 展开 figureId
  const [sales,   setSales]   = useState({});      // { figureId: [...] }

  /* ---------- 加载主表 ---------- */
  const load = async () => {
    const res = await getFigures();
    setRows(res.data);
  };
  useEffect(() => { load(); }, []);

  /* ---------- 下拉菜单选项：由 rows 动态计算 ---------- */
  const options = useMemo(() => {
    const uniq = (k) => [...new Set(rows.map(r => r[k]).filter(Boolean))].sort();
    return {
      manufacturer: uniq("manufacturer"),
      brand:        uniq("brand"),
      character:    uniq("character"),
      model_name:   uniq("model_name"),
      ip:           uniq("ip"),            // ← 新增
    };
  }, [rows]);

  /* ---------- 过滤后的行 ---------- */
  const filtered = useMemo(
    () => rows.filter(r =>
      (!sel.manufacturer || r.manufacturer === sel.manufacturer) &&
      (!sel.brand        || r.brand        === sel.brand) &&
      (!sel.character    || r.character    === sel.character) &&
      (!sel.model_name   || r.model_name   === sel.model_name) &&
      (!sel.ip           || r.ip           === sel.ip)
    ),
    [rows, sel]
  );

  /* ---------- 获取销售明细 ---------- */
  const fetchSales = async (id) => {
    const res = await api.get(`/figures/${id}/sales`);
    setSales(prev => ({ ...prev, [id]: res.data }));
  };

  /* ---------- 删除 ---------- */
  const del = async (id) => {
    if (!confirm("确定删除？")) return;
    try { await deleteFigure(id); load(); }
    catch (e) { alert(e.response?.data?.detail || "删除失败"); }
  };

  /* ---------- 入 / 出库 ---------- */
  const move = async (id, type, qty, price=null) => {
    try {
      const fn = type === "IN" ? inbound : outbound;
      await fn({ figure_id:id, quantity:qty, sale_price:price });
      await load();                                 // 刷新主表
      if (type==="OUT" && expanded===id)            // 明细折叠处于展开
        await fetchSales(id);                       // 即时刷新明细
    } catch (e) {
      alert(e.response?.data?.detail || "操作失败");
    }
  };

  /* ---------- 折叠 / 展开 ---------- */
  const toggle = async (id) => {
    if (expanded === id) { setExpanded(null); return; }
    if (!sales[id]) await fetchSales(id);
    setExpanded(id);
  };

  /* ---------- 渲染 ---------- */
  return (
    <>
      {/* ───────── 工具栏 ───────── */}
      <div className="toolbar">
        <Link to="/new">➕ 新增</Link>

        {["manufacturer","brand","character","model_name","ip"].map(k => (
          <select key={k}
                  value={sel[k] || ""}
                  onChange={e =>
                    setSel(p => ({ ...p, [k]: e.target.value || undefined }))
                  }>
            <option value="">{k}</option>
            {options[k].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        ))}
        <button onClick={() => setSel({})}>清空</button>
      </div>

      {/* ───────── 主表 ───────── */}
      <table className="fig-table">
        <thead>
          <tr>
            <th>图片</th><th>厂家</th><th>品牌</th><th>角色</th><th>造型</th><th>IP</th>
            <th>成本</th><th>库存</th><th>总销售额</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(r => (
            <React.Fragment key={r.id}>
              {/* 主行 */}
              <tr>
                <td>{r.image_url && <img src={r.image_url} />}</td>
                <td>{r.manufacturer}</td><td>{r.brand}</td><td>{r.character}</td><td>{r.model_name}</td>
                <td>{r.ip || "-"}</td>
                <td>{r.cost_price}</td><td>{r.qty}</td><td>{r.total_sales.toFixed(2)}</td>
                <td>
                  <button onClick={() => toggle(r.id)}>
                    {expanded === r.id ? "收起" : "明细"}
                  </button>
                  <button onClick={() => setDialog({ id: r.id, type: "IN" })}>入库</button>
                  <button onClick={() => setDialog({ id: r.id, type: "OUT" })}>出库</button>
                  <button onClick={() => del(r.id)}>删除</button>
                </td>
              </tr>

              {/* 展开行：销售明细 */}
              {expanded === r.id && (
                <tr className="sales-row">
                  <td colSpan={10}>
                    <table className="sales-table">
                      <thead>
                        <tr><th>单价</th><th>数量</th><th>总价</th><th>出售时间</th></tr>
                      </thead>
                      <tbody>
                        {sales[r.id]?.length ? sales[r.id].map((s,i) => (
                          <tr key={i}>
                            <td>{(+s.sale_price).toFixed(2)}</td>
                            <td>{s.quantity}</td>
                            <td>{(+s.sale_price * s.quantity).toFixed(2)}</td>
                            <td>{new Date(s.moved_at).toLocaleString()}</td>
                          </tr>
                        )) : (
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
    </>
  );
}