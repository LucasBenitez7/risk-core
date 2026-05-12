import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/components/ui/StatusBadge";

describe("StatusBadge", () => {
  it("renders status text with underscores replaced by spaces", () => {
    render(<StatusBadge status="under_review" />);
    expect(screen.getByText("under review")).toBeInTheDocument();
  });

  it("applies green style for 'active'", () => {
    render(<StatusBadge status="active" />);
    const badge = screen.getByText("active");
    expect(badge.className).toContain("emerald");
  });

  it("applies red style for 'error'", () => {
    render(<StatusBadge status="error" />);
    const badge = screen.getByText("error");
    expect(badge.className).toContain("red");
  });

  it("applies default style for unknown status", () => {
    render(<StatusBadge status="unknown_xyz" />);
    const badge = screen.getByText("unknown xyz");
    expect(badge.className).toContain("slate");
  });
});
