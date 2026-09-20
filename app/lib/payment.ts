export function formatMoney(amount:number,currency="KES"){return `${currency} ${Number(amount||0).toLocaleString(undefined,{minimumFractionDigits:2})}`}
