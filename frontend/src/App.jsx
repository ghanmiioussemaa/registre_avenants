import React from "react";
import { Routes, Route } from "react-router-dom";
import { FlashProvider } from "./FlashContext.jsx";
import { RefreshProvider } from "./RefreshContext.jsx";
import Layout from "./Layout.jsx";
import Overview from "./pages/Overview.jsx";
import Avenants from "./pages/Avenants.jsx";
import AvenantDetail from "./pages/AvenantDetail.jsx";
import Contracts from "./pages/Contracts.jsx";
import ContractDetail from "./pages/ContractDetail.jsx";
import ErrorPage from "./pages/ErrorPage.jsx";

export default function App() {
  return (
    <FlashProvider>
      <RefreshProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Overview />} />
            <Route path="/avenants" element={<Avenants />} />
            <Route path="/avenants/:messageId" element={<AvenantDetail />} />
            <Route path="/contrats" element={<Contracts />} />
            <Route path="/contrats/:contractId" element={<ContractDetail />} />
            <Route
              path="*"
              element={<ErrorPage message="Introuvable." />}
            />
          </Route>
        </Routes>
      </RefreshProvider>
    </FlashProvider>
  );
}
