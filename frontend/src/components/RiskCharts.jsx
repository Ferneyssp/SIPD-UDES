import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { RISK_CHART_COLORS, RISK_LEVELS, RISK_ORDER } from "../utils/risk";

const AXIS = { fontSize: 12, fill: "#5b6776" };
const TOOLTIP_STYLE = { borderRadius: 8, border: "1px solid #dde3ea", fontSize: 13 };

/** Dona: distribución de estudiantes por nivel de riesgo (con leyenda y valores en texto). */
export function RiskDistributionChart({ totals }) {
  const data = [
    { code: "ALTO", name: "Alto", value: totals.high },
    { code: "MEDIO", name: "Medio", value: totals.medium },
    { code: "BAJO", name: "Bajo", value: totals.low },
  ];
  const total = data.reduce((sum, item) => sum + item.value, 0);
  return (
    <div className="chart-with-legend">
      <div className="chart-box donut" role="img" aria-label={`Distribución: ${data.map((d) => `${d.name} ${d.value}`).join(", ")}`}>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie isAnimationActive={false} data={data} dataKey="value" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={2} stroke="#fff" strokeWidth={2}>
              {data.map((item) => <Cell key={item.code} fill={RISK_CHART_COLORS[item.code]} />)}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value, name) => [`${value} estudiantes`, `Riesgo ${name}`]} />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center" aria-hidden="true">
          <strong>{total}</strong>
          <span>con predicción</span>
        </div>
      </div>
      <ul className="chart-legend">
        {data.map((item) => (
          <li key={item.code}>
            <span className={`legend-swatch ${RISK_LEVELS[item.code].className}-bg`} aria-hidden="true" />
            <span className="legend-label">{item.name}</span>
            <span className="legend-value">
              {item.value} <small>({total ? ((100 * item.value) / total).toFixed(1).replace(".", ",") : 0} %)</small>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Barras apiladas horizontales: estudiantes por nivel en cada programa. */
export function RiskByProgramChart({ rows }) {
  const data = rows.map((row) => ({ program: row.program.replace("Ingeniería", "Ing."), ALTO: row.ALTO, MEDIO: row.MEDIO, BAJO: row.BAJO }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 46 + 40)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }} barCategoryGap={10}>
        <CartesianGrid horizontal={false} stroke="#eef1f5" />
        <XAxis type="number" allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="program" width={120} tick={{ ...AXIS, fill: "#1f2a37", fontWeight: 600 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "#f3f6f9" }} formatter={(value, name) => [value, `Riesgo ${RISK_LEVELS[name]?.label || name}`]} />
        <Legend formatter={(value) => RISK_LEVELS[value]?.label || value} iconType="square" wrapperStyle={{ fontSize: 13 }} />
        {RISK_ORDER.map((code, index) => (
          <Bar
            isAnimationActive={false}
            key={code}
            dataKey={code}
            stackId="risk"
            fill={RISK_CHART_COLORS[code]}
            stroke="#fff"
            strokeWidth={2}
            radius={index === RISK_ORDER.length - 1 ? [0, 4, 4, 0] : 0}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Evolución del riesgo estimado de un estudiante, con los umbrales como referencia. */
export function RiskTimelineChart({ points, thresholds }) {
  const data = points.map((point) => ({ period: point.academic_period, riesgo: point.risk_percentage, level: point.risk_level }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 12, right: 24, bottom: 4, left: 0 }}>
        <CartesianGrid vertical={false} stroke="#eef1f5" />
        <XAxis dataKey="period" tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 100]} unit="%" tick={AXIS} axisLine={false} tickLine={false} width={48} />
        {thresholds && (
          <>
            <ReferenceLine y={thresholds.low * 100} stroke={RISK_CHART_COLORS.MEDIO} strokeDasharray="4 4"
              label={{ value: `Medio ≥ ${thresholds.low * 100}%`, position: "insideTopRight", fontSize: 11, fill: "#5b6776" }} />
            <ReferenceLine y={thresholds.medium * 100} stroke={RISK_CHART_COLORS.ALTO} strokeDasharray="4 4"
              label={{ value: `Alto ≥ ${thresholds.medium * 100}%`, position: "insideTopRight", fontSize: 11, fill: "#5b6776" }} />
          </>
        )}
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value, _name, item) => [`${value} % (${RISK_LEVELS[item.payload.level]?.label})`, "Riesgo estimado"]}
        />
        <Line isAnimationActive={false} type="monotone" dataKey="riesgo" stroke="#1d3a5c" strokeWidth={2}
          dot={{ r: 5, strokeWidth: 2, fill: "#fff" }} activeDot={{ r: 7 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
