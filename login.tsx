import React, { useState, useEffect } from "react";
import { Redirect, useLocation } from "react-router-dom";
import { connect, useSelector } from "react-redux";
import type { InjectedFormProps, DecoratedFormProps } from "redux-form";
import { reduxForm, formValueSelector, isDirty } from "redux-form";
import {
  LOGIN_FORM_NAME,
  LOGIN_FORM_EMAIL_FIELD_NAME,
  LOGIN_FORM_PASSWORD_FIELD_NAME,
} from "@appsmith/constants/forms";
import { FORGOT_PASSWORD_URL, SETUP, SIGN_UP_URL } from "constants/routes";
import {
  LOGIN_PAGE_TITLE,
  LOGIN_PAGE_EMAIL_INPUT_LABEL,
  LOGIN_PAGE_PASSWORD_INPUT_LABEL,
  LOGIN_PAGE_PASSWORD_INPUT_PLACEHOLDER,
  LOGIN_PAGE_EMAIL_INPUT_PLACEHOLDER,
  FORM_VALIDATION_EMPTY_PASSWORD,
  FORM_VALIDATION_INVALID_EMAIL,
  LOGIN_PAGE_LOGIN_BUTTON_TEXT,
  LOGIN_PAGE_FORGOT_PASSWORD_TEXT,
  LOGIN_PAGE_SIGN_UP_LINK_TEXT,
  LOGIN_PAGE_INVALID_CREDS_ERROR,
  LOGIN_PAGE_INVALID_CREDS_FORGOT_PASSWORD_LINK,
  NEW_TO_APPSMITH,
  createMessage,
  LOGIN_PAGE_SUBTITLE,
} from "@appsmith/constants/messages";
import { FormGroup } from "design-system-old";
import { Button, Link, Callout } from "design-system";
import FormTextField from "components/utils/ReduxFormTextField";
import ThirdPartyAuth from "pages/UserAuth/ThirdPartyAuth";
import { isEmail, isEmptyString } from "utils/formhelpers";
import type { LoginFormValues } from "pages/UserAuth/helpers";

import { SpacedSubmitForm, FormActions } from "pages/UserAuth/StyledComponents";
import AnalyticsUtil from "utils/AnalyticsUtil";
import { LOGIN_SUBMIT_PATH } from "@appsmith/constants/ApiConstants";
import PerformanceTracker, {
  PerformanceTransactionName,
} from "utils/PerformanceTracker";
import { getIsSafeRedirectURL } from "utils/helpers";
import { getCurrentUser } from "selectors/usersSelectors";
import Container from "pages/UserAuth/Container";
import {
  getThirdPartyAuths,
  getIsFormLoginEnabled,
  getTenantConfig,
} from "@appsmith/selectors/tenantSelectors";
import Helmet from "react-helmet";
import { useFeatureFlag } from "utils/hooks/useFeatureFlag";
import { FEATURE_FLAG } from "@appsmith/entities/FeatureFlag";
import { getHTMLPageTitle } from "@appsmith/utils/BusinessFeatures/brandingPageHelpers";

const validate = (values: LoginFormValues, props: ValidateProps) => {
  const errors: LoginFormValues = {};
  const email = values[LOGIN_FORM_EMAIL_FIELD_NAME] || "";
  const password = values[LOGIN_FORM_PASSWORD_FIELD_NAME];
  const { isPasswordFieldDirty, touch } = props;
  if (!password || isEmptyString(password)) {
    isPasswordFieldDirty && touch?.(LOGIN_FORM_PASSWORD_FIELD_NAME);
    errors[LOGIN_FORM_PASSWORD_FIELD_NAME] = createMessage(
      FORM_VALIDATION_EMPTY_PASSWORD,
    );
  }
  if (!isEmptyString(email) && !isEmail(email)) {
    touch?.(LOGIN_FORM_EMAIL_FIELD_NAME);
    errors[LOGIN_FORM_EMAIL_FIELD_NAME] = createMessage(
      FORM_VALIDATION_INVALID_EMAIL,
    );
  }

  return errors;
};

type LoginFormProps = {
  emailValue: string;
} & InjectedFormProps<LoginFormValues, { emailValue: string }>;

type ValidateProps = {
  isPasswordFieldDirty?: boolean;
} & DecoratedFormProps<
  LoginFormValues,
  { emailValue: string; isPasswordFieldDirty?: boolean }
>;

export function Login(props: LoginFormProps) {
  const { emailValue: email, error, valid } = props;
  const isFormValid = valid && email && !isEmptyString(email);
  const location = useLocation();
  const isFormLoginEnabled = useSelector(getIsFormLoginEnabled);
  const socialLoginList = useSelector(getThirdPartyAuths);
  const queryParams = new URLSearchParams(location.search);
  const isBrandingEnabled = useFeatureFlag(
    FEATURE_FLAG.license_branding_enabled,
  );
  const tenantConfig = useSelector(getTenantConfig);
  const { instanceName } = tenantConfig;
  const htmlPageTitle = getHTMLPageTitle(isBrandingEnabled, instanceName);
  const invalidCredsForgotPasswordLinkText = createMessage(
    LOGIN_PAGE_INVALID_CREDS_FORGOT_PASSWORD_LINK,
  );
  let showError = false;
  let errorMessage = "";
  const currentUser = useSelector(getCurrentUser);
  if (currentUser?.emptyInstance) {
    return <Redirect to={SETUP} />;
  }
  if (queryParams.get("error")) {
    errorMessage = queryParams.get("message") || queryParams.get("error") || "";
    showError = true;
  }
  let loginURL = "/api/v1/" + LOGIN_SUBMIT_PATH;
  let signupURL = SIGN_UP_URL;
  const redirectUrl = queryParams.get("redirectUrl");
  if (redirectUrl != null && getIsSafeRedirectURL(redirectUrl)) {
    const encodedRedirectUrl = encodeURIComponent(redirectUrl);
    loginURL += `?redirectUrl=${encodedRedirectUrl}`;
    signupURL += `?redirectUrl=${encodedRedirectUrl}`;
  }

  let forgotPasswordURL = `${FORGOT_PASSWORD_URL}`;
  if (props.emailValue && !isEmptyString(props.emailValue)) {
    forgotPasswordURL += `?email=${props.emailValue}`;
  }

  const footerSection = isFormLoginEnabled && (
    <div className="px-2 py-4 flex align-center justify-center text-base text-center text-[color:var(--ads-v2\-color-fg)] text-[14px]">
      {createMessage(NEW_TO_APPSMITH)}
      <Link
        className="t--sign-up t--signup-link pl-[var(--ads-v2\-spaces-3)]"
        kind="primary"
        target="_self"
        to={signupURL}
      >
        {createMessage(LOGIN_PAGE_SIGN_UP_LINK_TEXT)}
      </Link>
    </div>
  );

  const [iframeVisible, setIframeVisible] = useState(false);

  const handleButtonClick = () => {
    setIframeVisible(true);
  };

  const checkLocalStorage = () => {
    const user = localStorage.getItem('user');
    if (user) {
      // 请求接口
      fetch('/your-api-endpoint', {
        method: 'GET', // 或者 'POST' 根据你的需要
        headers: {
          'Authorization': `Bearer ${user}`
        }
      })
      .then(response => response.json())
      .then(data => {
        console.log(data);
        // 请求完成后5秒刷新页面
        setTimeout(() => {
          window.location.reload();
        }, 5000);
      })
      .catch(error => {
        console.error('Error:', error);
      });

      // 隐藏 iframe
      setIframeVisible(false);
    }
  };

  useEffect(() => {
    // 监听 local storage 变化
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'user') {
        checkLocalStorage();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    checkLocalStorage(); // 初次加载时检查

    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  return (
    <Container
      footer={footerSection}
      subtitle={createMessage(LOGIN_PAGE_SUBTITLE)}
      title={createMessage(LOGIN_PAGE_TITLE)}
    >
      <Helmet>
        <title>{htmlPageTitle}</title>
      </Helmet>

      {showError && (
        <Callout
          kind="error"
          links={
            !!errorMessage
              ? undefined
              : [
                  {
                    children: invalidCredsForgotPasswordLinkText,
                    to: FORGOT_PASSWORD_URL,
                  },
                ]
          }
        >
          {!!errorMessage && errorMessage !== "true"
            ? errorMessage
            : createMessage(LOGIN_PAGE_INVALID_CREDS_ERROR)}
        </Callout>
      )}
      {socialLoginList.length > 0 && (
        <ThirdPartyAuth logins={socialLoginList} type={"SIGNIN"} />
      )}
      {isFormLoginEnabled && (
        <>
          <SpacedSubmitForm action={loginURL} method="POST">
            <FormGroup
              intent={error ? "danger" : "none"}
              label={createMessage(LOGIN_PAGE_EMAIL_INPUT_LABEL)}
            >
              <FormTextField
                autoFocus
                name={LOGIN_FORM_EMAIL_FIELD_NAME}
                placeholder={createMessage(LOGIN_PAGE_EMAIL_INPUT_PLACEHOLDER)}
                type="email"
              />
            </FormGroup>
            <FormGroup
              intent={error ? "danger" : "none"}
              label={createMessage(LOGIN_PAGE_PASSWORD_INPUT_LABEL)}
            >
              <FormTextField
                name={LOGIN_FORM_PASSWORD_FIELD_NAME}
                placeholder={createMessage(
                  LOGIN_PAGE_PASSWORD_INPUT_PLACEHOLDER,
                )}
                type="password"
              />
            </FormGroup>

            <FormActions>
              <Button
                isDisabled={!isFormValid}
                kind="primary"
                onClick={() => {
                  PerformanceTracker.startTracking(
                    PerformanceTransactionName.LOGIN_CLICK,
                  );
                  AnalyticsUtil.logEvent("LOGIN_CLICK", {
                    loginMethod: "EMAIL",
                  });
                }}
                size="md"
                type="submit"
              >
                {createMessage(LOGIN_PAGE_LOGIN_BUTTON_TEXT)}
              </Button>
            </FormActions>
          </SpacedSubmitForm>
          <Link
            className="justify-center"
            target="_self"
            to={forgotPasswordURL}
          >
            {createMessage(LOGIN_PAGE_FORGOT_PASSWORD_TEXT)}
          </Link>
        </>
      )}
      <Button onClick={handleButtonClick}>打开iframe</Button>
      {iframeVisible && (
        <div style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '80%',
          height: '80%',
          backgroundColor: 'white',
          border: '1px solid #ccc',
          zIndex: 1000,
          boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)',
        }}>
          <iframe
            src="https://your-iframe-url.com"
            style={{ width: '100%', height: '100%', border: 'none' }}
          ></iframe>
          <Button onClick={() => setIframeVisible(false)} style={{
            position: 'absolute',
            top: '10px',
            right: '10px',
          }}>关闭</Button>
        </div>
      )}
    </Container>
  );
}

const selector = formValueSelector(LOGIN_FORM_NAME);
export default connect((state) => ({
  emailValue: selector(state, LOGIN_FORM_EMAIL_FIELD_NAME),
  isPasswordFieldDirty: isDirty(LOGIN_FORM_NAME)(
    state,
    LOGIN_FORM_PASSWORD_FIELD_NAME,
  ),
}))(
  reduxForm<LoginFormValues, { emailValue: string }>({
    validate,
    touchOnBlur: false,
    form: LOGIN_FORM_NAME,
  })(Login),
);
