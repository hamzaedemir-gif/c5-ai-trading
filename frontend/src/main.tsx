import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { Dashboard } from "./pages/Dashboard";
import { StockDetail } from "./pages/StockDetail";
import { Layout } from "./components/Layout";
import { LiveDataProvider } from "./live/LiveDataProvider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <LiveDataProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/stocks/:symbol" element={<StockDetail />} />
          </Routes>
        </Layout>
      </LiveDataProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
