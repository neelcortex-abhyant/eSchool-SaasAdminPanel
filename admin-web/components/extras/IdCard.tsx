"use client";

import { useCallback } from "react";
import { useOptions } from "@/components/academics/hooks";
import { ownSchool } from "@/lib/domains/school";
import type { CardKind } from "@/lib/extras/idCards";

export type CardSchool = { name: string; logo: string | null; address: string | null; phone: string | null };

export type CardData = {
  kind: CardKind;
  title: string;
  /** Up to five label/value pairs on the front. */
  lines: [string, string][];
  image: string | null;
  front: string | null;
  back: string | null;
  /** A QR code or barcode image from the server, when it makes one. */
  code?: string | null;
};

/** The school's name, logo, address and phone for the card header and back, from /school-admin/school. */
export function useCardSchool(): CardSchool {
  const state = useOptions(
    useCallback(
      () =>
        ownSchool()
          .then((school) => [{ name: school.name || "School", logo: safeImage(school.logo), address: school.address || null, phone: school.support_phone || null }])
          .catch(() => [{ name: "School", logo: null, address: null, phone: null }]),
      [],
    ),
  );
  return state.options[0] ?? { name: "School", logo: null, address: null, phone: null };
}

/** Only web or site-relative image addresses are shown. */
export function safeImage(value: string | null | undefined): string | null {
  if (!value) return null;
  return /^https?:\/\//i.test(value) || value.startsWith("/") || /^data:image\/(png|jpeg|gif|svg\+xml);base64,/i.test(value) ? value : null;
}

export function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "?"
  );
}

/** One ID card, front and back, at CR80 size (85.6 × 54 mm) when printed. */
export function IdCardView({ card, school }: { card: CardData; school: CardSchool }) {
  const label = card.kind === "student" ? "Student" : "Staff";
  const image = safeImage(card.image);
  return (
    <div className={`idc-pair is-${card.kind}`}>
      <article className="idc idc-front" aria-label={`${label} ID card, front`}>
        <header className="idc-band">
          {school.logo ? <img className="idc-logo" src={school.logo} alt="" /> : <span className="idc-logo idc-logo-text">{initials(school.name)}</span>}
          <span className="idc-school">{school.name}</span>
          <span className="idc-kind">{label}</span>
        </header>
        <div className="idc-body">
          {image ? <img className="idc-photo" src={image} alt="" /> : <span className="idc-photo idc-photo-text">{initials(card.title)}</span>}
          <div className="idc-details">
            <strong className="idc-name">{card.title}</strong>
            <dl>
              {card.lines.slice(0, 5).map(([name, value]) => (
                <div key={name}>
                  <dt>{name}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
        {safeImage(card.code) ? <img className="idc-code" src={safeImage(card.code) as string} alt="QR code" /> : null}
        {card.front ? <p className="idc-note">{card.front}</p> : null}
      </article>
      <article className="idc idc-back" aria-label={`${label} ID card, back`}>
        <header className="idc-band idc-band-thin">
          <span className="idc-school">{school.name}</span>
        </header>
        <div className="idc-back-body">
          {card.back ? <p className="idc-back-text">{card.back}</p> : null}
          {school.address ? <p className="idc-small">{school.address}</p> : null}
          {school.phone ? <p className="idc-small">Phone: {school.phone}</p> : null}
          <p className="idc-small idc-return">If found, please return to the school.</p>
        </div>
      </article>
    </div>
  );
}
