import { Fragment } from "react";
import { BRAND_NAME, OPERATOR_NAME, legalLabel, legalValue } from "@/lib/legal/config";

/** Replaces {{token}} with configured values; unconfigured legal details render as a visible placeholder. */
export default function LegalText({ text }: { text: string }) {
  const parts = text.split(/(\{\{\w+\}\})/g);
  return (
    <>
      {parts.map((part, index) => {
        const match = part.match(/^\{\{(\w+)\}\}$/);
        if (!match) return <Fragment key={index}>{part}</Fragment>;
        const key = match[1];
        if (key === "brand") return <Fragment key={index}>{BRAND_NAME}</Fragment>;
        if (key === "operator") return <Fragment key={index}>{OPERATOR_NAME}</Fragment>;
        if (key === "year") return <Fragment key={index}>{new Date().getFullYear()}</Fragment>;
        const value = legalValue(key);
        return value ? (
          <Fragment key={index}>{value}</Fragment>
        ) : (
          <mark className="legal-placeholder" key={index} title="The platform owner has not provided this yet">
            [TO BE PROVIDED: {legalLabel(key)}]
          </mark>
        );
      })}
    </>
  );
}
