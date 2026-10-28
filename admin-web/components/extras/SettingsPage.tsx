"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage, FieldInput } from "@/components/extras/Frame";
import { Chip, Stat } from "@/components/teaching/Frame";
import { displayValue, getOne, labelFor, replace } from "@/lib/extras/api";
import { initialValues, problems, readPath, toBody, type Values } from "@/lib/extras/form";
import type { ReportConfig, SettingsConfig } from "@/lib/extras/types";

/** Loads a settings object, edits it and saves it with PUT. */
export function SettingsPage({ config, icon }: { config: SettingsConfig; icon: ReactNode }) {
  return (
    <ExtrasPage title={config.title} description={config.description} icon={icon} note={config.note}>
      <SettingsBody config={config} />
    </ExtrasPage>
  );
}

function SettingsBody({ config }: { config: SettingsConfig }) {
  const toast = useToast();
  const state = useOptions(useCallback(() => getOne(config.path).then((row) => [row]), [config]));
  const [values, setValues] = useState<Values | null>(null);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const row = state.options[0];

  useEffect(() => {
    if (row) setValues(initialValues(config.fields, row));
  }, [row, config]);

  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (!values) return <div className="resource-card"><div className="skeleton" style={{ height: 160 }} /></div>;

  async function save() {
    if (!values) return;
    const invalid = problems(config.fields, values, false);
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await replace(config.path, { ...(config.extraBody ?? {}), ...toBody(config.fields, values, false) });
      toast("success", "Settings saved.");
      void state.reload();
    } catch (caught) {
      errors.fromError(caught, "Unable to save the settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      className="resource-card resource-fields"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      {errors.formError ? <div className="alert alert-danger field-span">{errors.formError}</div> : null}
      {config.status ? (
        <p className="field-span">
          {readPath(row ?? {}, config.status.key) ? <Chip tone="green">{config.status.yes}</Chip> : <Chip tone="grey">{config.status.no}</Chip>}
        </p>
      ) : null}
      {config.fields.map((field) => (
        <FieldInput key={field.key} field={field} value={values[field.key] ?? ""} error={errors.fieldErrors[field.key]} onChange={(value) => setValues((current) => ({ ...(current ?? {}), [field.key]: value }))} />
      ))}
      <div className="field-span">
        <button className="btn-pill btn-pill-green ops-inline-btn" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
      </div>
    </form>
  );
}

/** Figures from GET routes: numbers as tiles, breakdowns (objects) as small tables. */
export function ReportPage({ config, icon }: { config: ReportConfig; icon: ReactNode }) {
  return (
    <ExtrasPage title={config.title} description={config.description} icon={icon}>
      <ReportBody config={config} />
    </ExtrasPage>
  );
}

export function formatFigure(key: string, value: unknown, money: string[] = []): string {
  if (typeof value === "number" && (money.includes(key) || /amount|total$|_total|net|collected|income|expense/.test(key) && !/count|^total$|staff|students/.test(key))) {
    return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  }
  return typeof value === "number" ? value.toLocaleString("en-IN") : displayValue(value);
}

function ReportBody({ config }: { config: ReportConfig }) {
  const state = useOptions(useCallback(() => Promise.all(config.paths.map((item) => getOne(item.path))), [config]));
  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (state.loading && !state.options.length) return <div className="resource-card"><div className="skeleton" style={{ height: 160 }} /></div>;
  return (
    <>
      {config.paths.map((item, index) => {
        const data = state.options[index] ?? {};
        const figures = Object.entries(data).filter(([key, value]) => key !== "school_id" && (typeof value !== "object" || value === null));
        const groups = Object.entries(data).filter(([, value]) => value && typeof value === "object" && !Array.isArray(value)) as [string, Record<string, unknown>][];
        return (
          <section key={item.path} className="resource-card" aria-label={item.title}>
            {config.paths.length > 1 ? <h2>{item.title}</h2> : null}
            <div className="teach-stats">
              {figures.map(([key, value]) => (
                <Stat key={key} label={labelFor(key)} value={formatFigure(key, value, config.money)} />
              ))}
            </div>
            {groups.map(([key, values]) => (
              <div key={key} className="table-wrap">
                <table className="data-table acad-table">
                  <caption className="muted">{labelFor(key)}</caption>
                  <tbody>
                    {Object.entries(values).map(([name, value]) => (
                      <tr key={name}>
                        <th scope="row">{labelFor(name)}</th>
                        <td>{formatFigure(name, value, config.money)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </section>
        );
      })}
    </>
  );
}
