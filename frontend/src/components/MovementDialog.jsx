import React from 'react'; 

export default function MovementDialog({ type, onSubmit, onClose }) {
  const handler = (e) => {
    e.preventDefault();
    const qtyVal = e.target.qty.value.trim();
    const qtyNum = Number(qtyVal);

    // 前端校验：必须为正整数
    if (!/^\d+$/.test(qtyVal) || qtyNum <= 0) {
      alert("Invalid number");
      return;
    }

    const priceNum =
      type === "OUT" ? Number(e.target.price.value) : null;

    onSubmit(qtyNum, priceNum);
  };

  return (
    <div className="dialog-mask" onClick={onClose}>
      <form className="dialog" onSubmit={handler} onClick={(e) => e.stopPropagation()}>
        <h3>{type === "IN" ? "入库" : "出库"}数量</h3>
        {/* step=1 + min=1 => 无法输入小数或 0 */}
        <input name="qty" type="number" step="1" min="1" required />
        {type === "OUT" && (
          <>
            <h3>售价</h3>
            <input name="price" type="number" step="0.01" min="0" required />
          </>
        )}
        <button>确定</button>
      </form>
    </div>
  );
}