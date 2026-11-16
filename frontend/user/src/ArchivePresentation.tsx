import { itemFacts, type ItemFacts } from "../../shared/itemPresentation";
import brandWordmark from "../../shared/brand/bumbum-wordmark-black.svg?no-inline";

export const editionLabel = (item: ItemFacts) => itemFacts(item).find(({ label }) => label === "发行编号")?.value.replace(/^#/, "").replace("/", " / ");

export function PageHeader({ href = "/mine", label = "我的数字物品", onBack }: { href?: string; label?: string; onBack?: () => void }) {
  const logo = <img className="brand-wordmark" src={brandWordmark} alt="bumbum" width={86} height={16} />;
  return <header className={onBack ? "brand brand--back" : "brand"}>
    {onBack ? <><button className="brand-caption" type="button" onClick={onBack}><span aria-hidden="true">←</span> {label}</button>{logo}</> :
      <>{logo}<a className="brand-caption" href={href}>{label} <span aria-hidden="true">→</span></a></>}
  </header>;
}

export function ItemIdentity({ name, item, owned = false }: { name: string; item: ItemFacts; owned?: boolean }) {
  const edition = editionLabel(item);
  return <div className="identity">
    <p className={owned ? "identity-status identity-status--owned" : "identity-status"}>{owned ? "你持有这件物品" : "已识别这件物品"}</p>
    <div className="identity-line">
      <h1>{name}</h1>
      {edition && <p className="edition"><span>发行编号</span><strong>{edition}</strong></p>}
    </div>
  </div>;
}

export function ItemMetadata({ item }: { item: ItemFacts & { item_uid: string } }) {
  return <dl className="item-metadata">
    {item.issue_name && <div><dt>发行系列</dt><dd>{item.issue_name}</dd></div>}
    <div><dt>物品编号</dt><dd className="item-number">{item.item_uid}</dd></div>
  </dl>;
}

export function ArchiveDetails({ material, care_instructions, description }: {
  material?: string | null; care_instructions?: string | null; description?: string | null;
}) {
  const care = [material?.trim(), care_instructions?.trim()].filter(Boolean).join(" ");
  return <>
    {care && <section className="profile-section">
      <h2>材质与养护</h2>
      <p>{care}</p>
    </section>}
    {description?.trim() && <section className="profile-section"><h2>物品介绍</h2><p>{description}</p></section>}
  </>;
}
