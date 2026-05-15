/* global React, ReactDOM, AndroidDevice, DesignCanvas, DCSection, DCArtboard,
   InboxApp, BoardApp, ReelApp */

// Wrap each variant inside an Android device frame at a consistent size.
const PhoneFrame = ({ children }) => (
  <AndroidDevice width={412} height={892} dark={true} title={undefined}>
    {children}
  </AndroidDevice>
);

const App = () => (
  <DesignCanvas>
    <DCSection
      id="mobile-review"
      title="Mobile review companion"
      subtitle="Logged in as Max Borg (FX Supervisor) · Reviewing publishes from the pipeline"
    >
      <DCArtboard id="a-inbox" label="A · Inbox feed" width={428} height={908}>
        <PhoneFrame><InboxApp/></PhoneFrame>
      </DCArtboard>
      <DCArtboard id="b-board" label="B · Project board" width={428} height={908}>
        <PhoneFrame><BoardApp/></PhoneFrame>
      </DCArtboard>
      <DCArtboard id="c-reel" label="C · Reel" width={428} height={908}>
        <PhoneFrame><ReelApp/></PhoneFrame>
      </DCArtboard>
    </DCSection>
  </DesignCanvas>
);

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
