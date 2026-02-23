import React from "react";
import { render, screen } from "@testing-library/react";
import HomePage from "../../app/page";

describe("homepage", () => {
  it("renders OmniFlow AI heading", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { name: "OmniFlow AI" })).toBeInTheDocument();
  });
});
