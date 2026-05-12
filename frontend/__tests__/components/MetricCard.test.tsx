import { render, screen } from "@testing-library/react";
import { MetricCard } from "@/components/ui/MetricCard";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Active policies" value={42} />);
    expect(screen.getByText("Active policies")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders hint when provided", () => {
    render(<MetricCard label="Open claims" value={7} hint="3 filed today" />);
    expect(screen.getByText("3 filed today")).toBeInTheDocument();
  });

  it("does not render hint element when omitted", () => {
    render(<MetricCard label="Rate" value="99%" />);
    // MetricCard renders 2 <p> elements (label + value); hint adds a 3rd
    expect(screen.queryAllByRole("paragraph")).toHaveLength(2);
  });
});
