import Image from "next/image";

export function Brand() {
  return <div className="brand"><span className="brandMark" aria-hidden="true"><Image src="/brand/agan-driving-logo.png" alt="" width={32} height={32} priority /></span><span>阿甘学车</span></div>;
}
